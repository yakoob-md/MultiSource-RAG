"""
backend/api/evaluation.py

REST endpoints for RAGAS Evaluation
POST /eval/start   — kicks off evaluation as a background job
GET  /eval/status/{job_id} — polls job progress & results
GET  /eval/results/{job_id} — returns final results JSON
"""

from __future__ import annotations

import threading
import time
import uuid
from typing import Any

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel

router = APIRouter()

# ── In-memory job store (survives for the backend session) ───────────────────
# Maps job_id -> {"status": "running"|"done"|"error", "progress": {...}, "result": {...}}
_jobs: dict[str, dict[str, Any]] = {}


class EvalStartRequest(BaseModel):
    n_questions: int = 15  # How many test questions to evaluate (5-30 recommended)
    agentic_mode: bool = False  # Whether to use the deep research pipeline


# ─────────────────────────────────────────────────────────────────────────────
# Background worker
# ─────────────────────────────────────────────────────────────────────────────

def _run_eval_job(job_id: str, n_questions: int, use_agentic: bool = False):
    """Runs in a background thread. Updates _jobs[job_id] progressively."""
    _jobs[job_id]["status"] = "running"
    _jobs[job_id]["progress"] = {"current": 0, "total": n_questions, "message": "Starting..."}

    try:
        # Import here to avoid circular imports at module load time
        from backend.rag.evaluator import run_evaluation
        from backend.rag.multi_retriever import MultiSourceResult
        from backend.rag.generator import generate_answer, _build_citations
        from backend.api.query import _safe_classify, _do_retrieve
        from backend.rag.agent_workflow import run_agentic_workflow

        def retriever_fn(question: str) -> MultiSourceResult:
            analysis = _safe_classify(question)
            
            # Normal retrieval function
            def base_retriever(q, sids):
                return _do_retrieve(q, sids, analysis)

            if use_agentic:
                # Use the agentic research workflow
                multi_result, _ = run_agentic_workflow(
                    question=question,
                    retriever_fn=base_retriever,
                    source_ids=None,
                    is_legal=False # Default to false for generic eval
                )
                return multi_result
            else:
                # Direct retrieval
                return base_retriever(question, None)

        def generator_fn(question: str, multi_result: MultiSourceResult) -> str:
            try:
                result = generate_answer(question, multi_result, history=None)
                return result.answer
            except Exception as e:
                return f"[Generation error: {e}]"

        def progress_cb(current: int, total: int, msg: str):
            mode_prefix = "[DEEP] " if use_agentic else "[NORMAL] "
            _jobs[job_id]["progress"] = {
                "current": current,
                "total": total,
                "message": mode_prefix + msg,
            }

        result = run_evaluation(
            retriever_fn=retriever_fn,
            generator_fn=generator_fn,
            n_questions=n_questions,
            progress_cb=progress_cb,
        )

        _jobs[job_id]["status"] = "done"
        _jobs[job_id]["result"] = result
        _jobs[job_id]["progress"]["message"] = "Evaluation complete!"

    except Exception as e:
        print(f"[EvalAPI] Job {job_id[:8]} failed: {e}")
        _jobs[job_id]["status"] = "error"
        _jobs[job_id]["error"] = str(e)


# ─────────────────────────────────────────────────────────────────────────────
# Endpoints
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/start")
def start_evaluation(req: EvalStartRequest):
    """
    POST /eval/start
    Kicks off a RAGAS evaluation run in the background.
    Returns a job_id to poll with GET /eval/status/{job_id}
    """
    # Limit concurrent jobs
    running = [j for j in _jobs.values() if j.get("status") == "running"]
    if running:
        raise HTTPException(
            status_code=409,
            detail="An evaluation is already running. Wait for it to finish.",
        )

    n = max(5, min(req.n_questions, 25))  # clamp 5-25 for Groq limits
    job_id = str(uuid.uuid4())
    _jobs[job_id] = {"status": "queued", "progress": {}, "result": None}

    t = threading.Thread(target=_run_eval_job, args=(job_id, n, req.agentic_mode), daemon=True)
    t.start()

    return {"job_id": job_id, "status": "queued", "n_questions": n}


@router.get("/status/{job_id}")
def get_eval_status(job_id: str):
    """
    GET /eval/status/{job_id}
    Returns current status, progress, and result (when done).
    Frontend polls this every 2 seconds.
    """
    if job_id not in _jobs:
        raise HTTPException(status_code=404, detail="Job not found")

    job = _jobs[job_id]
    response = {
        "job_id": job_id,
        "status": job.get("status"),
        "progress": job.get("progress", {}),
    }

    if job.get("status") == "done":
        response["result"] = job.get("result")

    if job.get("status") == "error":
        response["error"] = job.get("error")

    return response


@router.get("/jobs")
def list_jobs():
    """GET /eval/jobs — list all evaluation jobs (for debug)."""
    return [
        {
            "job_id": jid,
            "status": j.get("status"),
            "n_evaluated": j.get("result", {}).get("n_evaluated") if j.get("result") else None,
        }
        for jid, j in _jobs.items()
    ]
