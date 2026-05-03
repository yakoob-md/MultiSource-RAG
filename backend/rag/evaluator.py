"""
backend/rag/evaluator.py

RAGAS Evaluation Pipeline (Groq-powered judge)
===============================================
Runs Faithfulness, Answer Relevancy, and Context Precision evaluation
using Groq (llama-3.3-70b-versatile) as the judge LLM — no OpenAI needed.

Auto-generates test questions from your existing knowledge base so you
don't have to write them manually.
"""

from __future__ import annotations

import json
import time
import uuid
from typing import Any

from groq import Groq

from backend.config import GROQ_API_KEY, GROQ_MODEL
from backend.database.connection import get_connection

# ── Groq judge model ─────────────────────────────────────────────────────────
_JUDGE_MODEL = GROQ_MODEL  # llama-3.3-70b-versatile


def _groq() -> Groq:
    return Groq(api_key=GROQ_API_KEY)


# ─────────────────────────────────────────────────────────────────────────────
# STEP 1 — AUTO-GENERATE TEST QUESTIONS
# ─────────────────────────────────────────────────────────────────────────────

def generate_test_questions(n: int = 15) -> list[dict]:
    """
    Pulls random chunks from the database and asks Groq to generate
    a realistic question that could be answered from that chunk.
    Returns a list of {question, ground_truth_context, source_title} dicts.
    """
    print(f"[Evaluator] Generating {n} test questions from knowledge base...")

    # Pull n random chunks from MySQL
    try:
        with get_connection() as conn:
            cursor = conn.cursor(dictionary=True)
            cursor.execute(
                """
                SELECT c.id, c.chunk_text, s.title as source_title
                FROM chunks c
                JOIN sources s ON c.source_id = s.id
                WHERE LENGTH(c.chunk_text) > 200
                ORDER BY RAND()
                LIMIT %s
                """,
                (n,),
            )
            rows = cursor.fetchall()
    except Exception as e:
        print(f"[Evaluator] DB error fetching chunks: {e}")
        return []

    if not rows:
        return []

    test_cases = []
    client = _groq()

    for row in rows:
        chunk_text = (row.get("chunk_text") or "")[:800]
        source_title = row.get("source_title", "Unknown Source")

        prompt = [
            {
                "role": "system",
                "content": (
                    "You are a Senior Academic Examiner. Given a text passage, generate ONE "
                    "complex, reasoning-based question that can ONLY be answered by understanding the specific context of this passage. "
                    "Avoid simple 'what is' questions. Aim for 'how' or 'why' or 'what are the implications of'. "
                    "Return ONLY the question text."
                ),
            },
            {
                "role": "user",
                "content": f"Passage:\n{chunk_text}",
            },
        ]

        try:
            resp = client.chat.completions.create(
                model="llama-3.1-8b-instant",  # fast model for question gen
                messages=prompt,
                temperature=0.6,
                max_tokens=120,
                timeout=15,
            )
            question = resp.choices[0].message.content.strip().strip('"')
            if question:
                test_cases.append(
                    {
                        "question": question,
                        "ground_truth_context": chunk_text,
                        "source_title": source_title,
                    }
                )
        except Exception as e:
            print(f"[Evaluator] Question gen failed for chunk: {e}")

        # Rate limit buffer — 8b instant has high limits but be safe
        time.sleep(0.3)

    print(f"[Evaluator] Generated {len(test_cases)} test questions")
    return test_cases


# ─────────────────────────────────────────────────────────────────────────────
# STEP 2 — RUN RAGAS-STYLE METRICS (Groq as judge)
# ─────────────────────────────────────────────────────────────────────────────

def _score_faithfulness(question: str, answer: str, contexts: list[str], client: Groq) -> float:
    """
    Faithfulness: Does every claim in the answer exist in the provided context?
    Score: 0.0 – 1.0 (1.0 = fully grounded, 0.0 = hallucinated)
    """
    context_block = "\n---\n".join(contexts[:4])
    prompt = [
        {
            "role": "system",
            "content": (
                "You are a faithfulness judge. Given a question, an AI answer, and source contexts, "
                "score how faithfully the answer is grounded in the contexts (0.0 = completely fabricated, "
                "1.0 = every claim is directly supported). "
                "Return ONLY a single decimal number between 0.0 and 1.0. Nothing else."
            ),
        },
        {
            "role": "user",
            "content": (
                f"Question: {question}\n\n"
                f"Answer: {answer[:600]}\n\n"
                f"Contexts:\n{context_block[:1500]}"
            ),
        },
    ]
    try:
        resp = client.chat.completions.create(
            model=_JUDGE_MODEL, messages=prompt, temperature=0.0, max_tokens=10, timeout=20
        )
        return float(resp.choices[0].message.content.strip())
    except Exception:
        return 0.5  # neutral fallback


def _score_answer_relevancy(question: str, answer: str, client: Groq) -> float:
    """
    Answer Relevancy: Does the answer actually address what was asked?
    Score: 0.0 – 1.0
    """
    prompt = [
        {
            "role": "system",
            "content": (
                "You are a relevance judge. Score how well the given answer addresses the question. "
                "1.0 = perfectly addresses the question, 0.0 = completely off-topic. "
                "Return ONLY a single decimal number between 0.0 and 1.0."
            ),
        },
        {
            "role": "user",
            "content": f"Question: {question}\n\nAnswer: {answer[:600]}",
        },
    ]
    try:
        resp = client.chat.completions.create(
            model=_JUDGE_MODEL, messages=prompt, temperature=0.0, max_tokens=10, timeout=20
        )
        return float(resp.choices[0].message.content.strip())
    except Exception:
        return 0.5


def _score_context_precision(question: str, contexts: list[str], client: Groq) -> float:
    """
    Context Precision: Are the retrieved passages actually relevant to the question?
    Score: 0.0 – 1.0
    """
    if not contexts:
        return 0.0
    context_block = "\n---\n".join(contexts[:4])
    prompt = [
        {
            "role": "system",
            "content": (
                "You are a retrieval precision judge. Score how relevant the retrieved passages are "
                "to the question. 1.0 = all passages are directly relevant, 0.0 = none are relevant. "
                "Return ONLY a single decimal number between 0.0 and 1.0."
            ),
        },
        {
            "role": "user",
            "content": f"Question: {question}\n\nRetrieved Passages:\n{context_block[:1500]}",
        },
    ]
    try:
        resp = client.chat.completions.create(
            model=_JUDGE_MODEL, messages=prompt, temperature=0.0, max_tokens=10, timeout=20
        )
        return float(resp.choices[0].message.content.strip())
    except Exception:
        return 0.5


# ─────────────────────────────────────────────────────────────────────────────
# STEP 3 — FULL EVALUATION RUNNER
# ─────────────────────────────────────────────────────────────────────────────

def run_evaluation(
    retriever_fn,     # callable(question) -> MultiSourceResult
    generator_fn,     # callable(question, multi_result) -> str
    n_questions: int = 15,
    progress_cb=None, # optional callback(current, total, message) for SSE
) -> dict[str, Any]:
    """
    Full evaluation pipeline:
    1. Auto-generate test questions from DB
    2. Retrieve context + generate answer for each
    3. Score with Faithfulness, Answer Relevancy, Context Precision
    4. Return aggregate + per-question results

    Returns:
    {
        "summary": {"faithfulness": 0.85, "answer_relevancy": 0.91, "context_precision": 0.78},
        "per_question": [...],
        "n_evaluated": 15
    }
    """
    def _progress(current: int, total: int, msg: str):
        print(f"[Evaluator] ({current}/{total}) {msg}")
        if progress_cb:
            progress_cb(current, total, msg)

    # Step 1: Generate questions
    _progress(0, n_questions, "Generating test questions from knowledge base...")
    test_cases = generate_test_questions(n_questions)

    if not test_cases:
        return {"error": "No test questions could be generated. Make sure documents are uploaded."}

    client = _groq()
    per_question = []
    total = len(test_cases)

    faithfulness_scores = []
    relevancy_scores = []
    precision_scores = []

    for i, case in enumerate(test_cases):
        question = case["question"]
        _progress(i + 1, total, f"Evaluating: {question[:60]}...")

        try:
            # Retrieve context
            multi_result = retriever_fn(question)
            contexts = [c.chunk_text for c in multi_result.all_chunks[:8]]

            # Generate answer
            answer = generator_fn(question, multi_result)

            # Rate limit buffer between scoring calls
            time.sleep(0.5)

            # Score
            f_score = _score_faithfulness(question, answer, contexts, client)
            time.sleep(0.3)
            r_score = _score_answer_relevancy(question, answer, client)
            time.sleep(0.3)
            p_score = _score_context_precision(question, contexts, client)
            time.sleep(0.3)

            faithfulness_scores.append(f_score)
            relevancy_scores.append(r_score)
            precision_scores.append(p_score)

            per_question.append(
                {
                    "question": question,
                    "source_title": case.get("source_title", ""),
                    "answer_preview": answer[:200] + "..." if len(answer) > 200 else answer,
                    "faithfulness": round(f_score, 3),
                    "answer_relevancy": round(r_score, 3),
                    "context_precision": round(p_score, 3),
                    "avg_score": round((f_score + r_score + p_score) / 3, 3),
                }
            )
        except Exception as e:
            print(f"[Evaluator] Error on question '{question[:40]}': {e}")
            per_question.append(
                {
                    "question": question,
                    "source_title": case.get("source_title", ""),
                    "error": str(e),
                    "faithfulness": 0.0,
                    "answer_relevancy": 0.0,
                    "context_precision": 0.0,
                    "avg_score": 0.0,
                }
            )

    # Aggregate
    def _mean(lst):
        return round(sum(lst) / len(lst), 3) if lst else 0.0

    summary = {
        "faithfulness": _mean(faithfulness_scores),
        "answer_relevancy": _mean(relevancy_scores),
        "context_precision": _mean(precision_scores),
        "overall": _mean(faithfulness_scores + relevancy_scores + precision_scores),
    }

    _progress(total, total, "Evaluation complete!")
    print(f"[Evaluator] Summary: {summary}")

    return {
        "summary": summary,
        "per_question": per_question,
        "n_evaluated": len(per_question),
    }
