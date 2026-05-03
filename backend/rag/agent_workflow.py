"""
backend/rag/agent_workflow.py

4-Stage Agentic RAG Workflow
============================
Stage 1 — Planner   : Expands 1 question into 3-4 targeted search queries
Stage 2 — Searcher  : Runs each query against FAISS, merges + deduplicates chunks
Stage 3 — Validator : Scores & filters chunks, keeps only the most relevant ones
Stage 4 — Synthesizer: Handled by existing generate_answer_stream (no extra call)

Rate-limit strategy:
  - Stages 1 & 3 use llama-3.1-8b-instant (FREE tier, 6000 TPM, super fast)
  - Stage 4 (synthesis) uses llama-3.3-70b-versatile (main model, existing limit)
  - Total extra tokens per query: ~400 (planner) + ~300 (validator) = ~700 tokens
  - This is well within free Groq limits (~6000 tokens/min on 8b model)
"""

from __future__ import annotations

import json
import re
import time
from typing import Generator

from groq import Groq

from backend.config import GROQ_API_KEY, GROQ_MODEL
from backend.rag.multi_retriever import MultiSourceResult, _build_source_groups
from backend.rag.retriever import RetrievedChunk

# ── Small fast model for planner & validator (higher rate limits, cheaper) ──────
_FAST_MODEL = "llama-3.1-8b-instant"

# ── Max chunks to keep after validation ─────────────────────────────────────────
_MAX_FINAL_CHUNKS = 12


def _get_groq(api_key: str) -> Groq:
    return Groq(api_key=api_key)


# ─────────────────────────────────────────────────────────────────────────────
# STAGE 1 — PLANNER
# Input : raw user question
# Output: list of 3-4 targeted search queries (strings)
# ─────────────────────────────────────────────────────────────────────────────

def _stage1_planner(question: str, is_legal: bool) -> list[str]:
    """
    Uses a fast 8B model to decompose the user question into
    3-4 specific search queries covering different angles.
    Returns at most 4 queries (safe for rate limits).
    """
    if is_legal:
        domain_hint = (
            "You are a Senior Legal Researcher. The user is querying an Indian law database "
            "(IPC sections, Supreme Court/High Court judgments, statutes)."
        )
        angle_hint = (
            "Cover angles like: statutory provisions, landmark case precedents, "
            "procedural requirements, constitutional basis, and exceptions/amendments."
        )
    else:
        domain_hint = "You are an expert research analyst."
        angle_hint = (
            "Cover angles like: core concept, technical methods, key findings, "
            "real-world applications, and open challenges."
        )

    prompt = [
        {
            "role": "system",
            "content": (
                f"{domain_hint} "
                "Given a user question, generate EXACTLY 3 precise search queries "
                "that together cover the full answer space. "
                f"{angle_hint} "
                "Return ONLY a JSON array of 3 strings. No explanation, no numbering."
            ),
        },
        {
            "role": "user",
            "content": f"User question: {question}",
        },
    ]

    try:
        client = _get_groq(GROQ_API_KEY)
        resp = client.chat.completions.create(
            model=_FAST_MODEL,
            messages=prompt,
            temperature=0.3,
            max_tokens=250,
            timeout=15,
        )
        raw = resp.choices[0].message.content.strip()
        # Extract JSON array robustly
        match = re.search(r"\[.*\]", raw, re.DOTALL)
        if match:
            queries = json.loads(match.group())
            if isinstance(queries, list):
                # Always include the original question as the first query for safety
                all_queries = [question] + [str(q) for q in queries[:3]]
                return list(dict.fromkeys(all_queries))[:4]  # deduplicate, max 4
    except Exception as e:
        print(f"[AgentWorkflow] Planner failed ({e}), falling back to original question")

    # Safe fallback — original question only
    return [question]


# ─────────────────────────────────────────────────────────────────────────────
# STAGE 2 — SEARCHER
# Input : list of queries, retriever function, source_ids filter
# Output: merged deduplicated list of RetrievedChunk
# ─────────────────────────────────────────────────────────────────────────────

def _stage2_searcher(
    queries: list[str],
    retriever_fn,          # callable(question, source_ids) -> MultiSourceResult
    source_ids: list[str] | None,
) -> list[RetrievedChunk]:
    """
    Runs every query through the FAISS retriever and merges results.
    Deduplicates by chunk_id so no duplicate text reaches the LLM.
    """
    seen_ids: set[str] = set()
    all_chunks: list[RetrievedChunk] = []

    for q in queries:
        try:
            result: MultiSourceResult = retriever_fn(q, source_ids)
            for chunk in result.all_chunks:
                if chunk.chunk_id not in seen_ids:
                    seen_ids.add(chunk.chunk_id)
                    all_chunks.append(chunk)
        except Exception as e:
            print(f"[AgentWorkflow] Searcher error for query '{q[:40]}': {e}")
        # Small sleep to avoid hammering the embedder back-to-back
        time.sleep(0.05)

    print(f"[AgentWorkflow] Searcher: {len(queries)} queries → {len(all_chunks)} unique chunks")
    return all_chunks


# ─────────────────────────────────────────────────────────────────────────────
# STAGE 3 — VALIDATOR
# Input : list of RetrievedChunk + original question
# Output: filtered top-N chunks, ranked by relevance
# ─────────────────────────────────────────────────────────────────────────────

def _stage3_validator(
    question: str,
    chunks: list[RetrievedChunk],
    max_chunks: int = _MAX_FINAL_CHUNKS,
) -> list[RetrievedChunk]:
    """
    Uses the fast 8B model to score each chunk's relevance to the question.
    Returns only the top-N highest-scoring chunks.

    To save tokens we only call the LLM if we have >max_chunks chunks.
    Otherwise, just return them sorted by existing similarity score.
    """
    if len(chunks) <= max_chunks:
        # Already small enough — sort by similarity score descending
        return sorted(chunks, key=lambda c: c.score, reverse=True)

    # Build a compact scoring prompt — one snippet per chunk
    snippets = "\n".join(
        f"[{i+1}] {c.chunk_text[:200].strip()}"
        for i, c in enumerate(chunks[:20])  # cap at 20 to avoid token overflow
    )

    prompt = [
        {
            "role": "system",
            "content": (
                "You are a relevance judge. Given a question and a list of text excerpts, "
                f"return ONLY a JSON array of the indices (1-based) of the top {max_chunks} "
                "most relevant excerpts, ordered best-first. "
                "Example output: [3, 1, 7, 5, 2, 9, 4, 6, 8, 10, 11, 12]"
            ),
        },
        {
            "role": "user",
            "content": f"Question: {question}\n\nExcerpts:\n{snippets}",
        },
    ]

    try:
        client = _get_groq(GROQ_API_KEY)
        resp = client.chat.completions.create(
            model=_FAST_MODEL,
            messages=prompt,
            temperature=0.0,
            max_tokens=100,
            timeout=15,
        )
        raw = resp.choices[0].message.content.strip()
        match = re.search(r"\[.*\]", raw, re.DOTALL)
        if match:
            indices = json.loads(match.group())
            selected = []
            for idx in indices:
                if isinstance(idx, int) and 1 <= idx <= len(chunks):
                    selected.append(chunks[idx - 1])
                if len(selected) >= max_chunks:
                    break
            if selected:
                print(f"[AgentWorkflow] Validator: {len(chunks)} → {len(selected)} chunks selected")
                return selected
    except Exception as e:
        print(f"[AgentWorkflow] Validator failed ({e}), falling back to score sort")

    # Fallback: sort by similarity score
    return sorted(chunks, key=lambda c: c.score, reverse=True)[:max_chunks]


# ─────────────────────────────────────────────────────────────────────────────
# MAIN ENTRY POINT
# ─────────────────────────────────────────────────────────────────────────────

def run_agentic_workflow(
    question: str,
    retriever_fn,
    source_ids: list[str] | None = None,
    is_legal: bool = False,
) -> tuple[MultiSourceResult, list[str]]:
    """
    Runs the 3-stage agentic pre-processing pipeline (Stage 4 / Synthesis
    is handled by the existing generate_answer_stream call in query.py).

    Returns:
        (MultiSourceResult, status_log)
        - MultiSourceResult: enriched context with more + better chunks
        - status_log: list of progress messages to stream to the UI
    """
    status_log: list[str] = []

    # ── Stage 1: Planner ──────────────────────────────────────────────────────
    print("[AgentWorkflow] Stage 1: Planning queries...")
    status_log.append("🧠 Planner: Decomposing your question into research angles...")
    queries = _stage1_planner(question, is_legal)
    status_log.append(f"🔎 Planner found {len(queries)} research angles to investigate")

    # ── Stage 2: Searcher ─────────────────────────────────────────────────────
    print(f"[AgentWorkflow] Stage 2: Searching {len(queries)} queries...")
    status_log.append(f"📚 Searcher: Running {len(queries)} targeted searches across your knowledge base...")
    all_chunks = _stage2_searcher(queries, retriever_fn, source_ids)
    status_log.append(f"✅ Searcher retrieved {len(all_chunks)} unique passages")

    # ── Stage 3: Validator ────────────────────────────────────────────────────
    print("[AgentWorkflow] Stage 3: Validating and ranking chunks...")
    status_log.append("⚖️  Validator: Scoring passages for relevance and quality...")
    validated_chunks = _stage3_validator(question, all_chunks)
    status_log.append(f"✨ Validator selected top {len(validated_chunks)} most relevant passages")

    # ── Build final MultiSourceResult ─────────────────────────────────────────
    source_groups = _build_source_groups(validated_chunks)
    result = MultiSourceResult(
        query_intent="synthesis" if len(source_groups) > 1 else "single_source",
        source_groups=source_groups,
        all_chunks=validated_chunks,
        source_count=len(source_groups),
    )

    print(f"[AgentWorkflow] Complete: {len(validated_chunks)} chunks from {len(source_groups)} sources")
    return result, status_log
