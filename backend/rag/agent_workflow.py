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
# Reduced from 12 to 8 to increase context density and reduce "lost in the middle"
_MAX_FINAL_CHUNKS = 8


def _get_groq(api_key: str) -> Groq:
    return Groq(api_key=api_key)


# ─────────────────────────────────────────────────────────────────────────────
# STAGE 1 — PLANNER
# ─────────────────────────────────────────────────────────────────────────────

def _stage1_planner(question: str, is_legal: bool) -> list[str]:
    """
    Uses a few-shot approach to generate 3 targeted queries.
    """
    if is_legal:
        domain_examples = (
            "Example 1: 'Does the IT Act 2000 apply to crypto?' -> ['Section 66 IT Act crypto', 'Indian crypto legality IPC', 'RBI digital asset circulars']\n"
            "Example 2: 'Bail for non-bailable offense' -> ['Section 437 CrPC conditions', 'Supreme Court bail guidelines', 'Anticipatory bail landmark cases']"
        )
        system_prompt = (
            "You are a Senior Legal Research Planner. Decompose the user question into 3 precise legal search queries. "
            "Focus on: Statutory sections, Case Law, and Procedural guidelines.\n"
            f"{domain_examples}\n"
            "Return ONLY a JSON array of 3 strings."
        )
    else:
        domain_examples = (
            "Example 1: 'How does BERT work?' -> ['BERT architecture transformer', 'Self-attention mechanism BERT', 'BERT pre-training MLM NSP']\n"
            "Example 2: 'Climate change impact on farming' -> ['Climate change crop yield statistics', 'Sustainable farming adaptations', 'Soil degradation carbon cycles']"
        )
        system_prompt = (
            "You are an expert Research Planner. Decompose the user question into 3 targeted search queries. "
            "Focus on: Technical foundations, Methodology, and Current Benchmarks.\n"
            f"{domain_examples}\n"
            "Return ONLY a JSON array of 3 strings."
        )

    prompt = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"Question: {question}"},
    ]

    try:
        client = _get_groq(GROQ_API_KEY)
        resp = client.chat.completions.create(
            model=_FAST_MODEL,
            messages=prompt,
            temperature=0.1, # Lower for consistency
            max_tokens=250,
        )
        raw = resp.choices[0].message.content.strip()
        match = re.search(r"\[.*\]", raw, re.DOTALL)
        if match:
            queries = json.loads(match.group())
            if isinstance(queries, list):
                # We always prioritize the original question
                all_queries = [question] + [str(q) for q in queries[:3]]
                return list(dict.fromkeys(all_queries))[:4]
    except Exception as e:
        print(f"[AgentWorkflow] Planner error: {e}")

    return [question]


# ─────────────────────────────────────────────────────────────────────────────
# STAGE 2 — SEARCHER
# ─────────────────────────────────────────────────────────────────────────────

def _stage2_searcher(
    queries: list[str],
    retriever_fn,
    source_ids: list[str] | None,
) -> list[RetrievedChunk]:
    seen_ids: set[str] = set()
    all_chunks: list[RetrievedChunk] = []

    for i, q in enumerate(queries):
        try:
            result: MultiSourceResult = retriever_fn(q, source_ids)
            for chunk in result.all_chunks:
                if chunk.chunk_id not in seen_ids:
                    seen_ids.add(chunk.chunk_id)
                    # We slightly boost the original question's chunks
                    if i == 0:
                        chunk.score *= 1.1
                    all_chunks.append(chunk)
        except Exception:
            pass
        time.sleep(0.02)

    return all_chunks


# ─────────────────────────────────────────────────────────────────────────────
# STAGE 3 — VALIDATOR (HYBRID)
# ─────────────────────────────────────────────────────────────────────────────

def _stage3_validator(
    question: str,
    chunks: list[RetrievedChunk],
    max_chunks: int = _MAX_FINAL_CHUNKS,
) -> list[RetrievedChunk]:
    """
    Combines LLM relevance scoring with Vector similarity (Hybrid).
    """
    if not chunks: return []
    if len(chunks) <= 3: return chunks # Too few to filter

    # Limit chunks to validate to avoid token limits (top 15 by vector score)
    candidate_chunks = sorted(chunks, key=lambda c: c.score, reverse=True)[:15]

    snippets = "\n".join(
        f"ID {i}: {c.chunk_text[:350].strip()}"
        for i, c in enumerate(candidate_chunks)
    )

    prompt = [
        {
            "role": "system",
            "content": (
                "You are an Elite Document Validator. Rate the relevance of each document snippet to the question. "
                "Return a JSON object where keys are IDs and values are integer scores from 0 (useless) to 10 (perfect answer).\n"
                "Example: {'0': 9, '1': 2, '2': 7}"
            ),
        },
        {
            "role": "user",
            "content": f"Question: {question}\n\nSnippets:\n{snippets}",
        },
    ]

    try:
        client = _get_groq(GROQ_API_KEY)
        resp = client.chat.completions.create(
            model=_FAST_MODEL,
            messages=prompt,
            temperature=0.0,
            max_tokens=200,
            response_format={"type": "json_object"}
        )
        llm_scores = json.loads(resp.choices[0].message.content)
        
        # Apply Hybrid Scoring: 70% LLM + 30% FAISS
        for i, chunk in enumerate(candidate_chunks):
            llm_val = float(llm_scores.get(str(i), llm_scores.get(i, 5)))
            # Normalize vector score (usually -10 to 10 or 0 to 1)
            # We assume a base score of 5 if LLM fails
            chunk.score = (llm_val * 1.5) + (chunk.score * 0.5)

        # Sort by hybrid score and take top N
        final = sorted(candidate_chunks, key=lambda c: c.score, reverse=True)[:max_chunks]
        return final
    except Exception as e:
        print(f"[AgentWorkflow] Validator error: {e}")
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
    status_log: list[str] = []

    # Planner
    status_log.append("🧠 Planner: Thinking across multiple research dimensions...")
    queries = _stage1_planner(question, is_legal)
    status_log.append(f"🎯 Planner: Targeting {len(queries)} specific data angles")
    time.sleep(1)

    # Searcher
    status_log.append("📚 Searcher: Parallel retrieval in progress...")
    all_chunks = _stage2_searcher(queries, retriever_fn, source_ids)
    status_log.append(f"🔎 Searcher: Found {len(all_chunks)} potential evidence blocks")
    time.sleep(1)

    # Validator
    status_log.append("⚖️ Validator: Hybrid re-ranking for maximum precision...")
    validated_chunks = _stage3_validator(question, all_chunks)
    
    # Calculate a simple "Confidence" based on top chunk score
    confidence = "High" if len(validated_chunks) > 0 and validated_chunks[0].score > 12 else "Medium"
    status_log.append(f"✨ Validator: {confidence} confidence context finalized ({len(validated_chunks)} blocks)")

    source_groups = _build_source_groups(validated_chunks)
    result = MultiSourceResult(
        query_intent="synthesis",
        source_groups=source_groups,
        all_chunks=validated_chunks,
        source_count=len(source_groups),
    )

    status_log.append("🖋️ Synthesizer: Drafting Professional Research Memorandum...")

    return result, status_log
