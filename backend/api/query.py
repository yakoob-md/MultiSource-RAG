# backend/api/query.py — FIXED: Multi-source, context, and history

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from backend.rag.retriever import retrieve
from backend.rag.generator import generate_answer_stream, _build_citations
from backend.rag.query_classifier import classify_query, QueryAnalysis, extract_source_filter
from backend.rag.multi_retriever import (
    MultiSourceResult, multi_retrieve, retrieve_multi_selected, retrieve_single_source
)
from backend.rag.multi_generator import generate_multi_answer
from backend.rag.image_rag import enrich_query_with_image_context
from backend.database.connection import get_connection
import uuid
import json

router = APIRouter()


class ChatMessageModel(BaseModel):
    role   : str
    content: str


class QueryRequest(BaseModel):
    question        : str
    source_ids      : list[str] | None = None
    history         : list[ChatMessageModel] | None = None
    mode            : str | None = None
    conversation_id : str | None = None
    image_id        : str | None = None
    include_images  : bool = False
    llm_provider    : str | None = "groq"


def _history_to_dicts(history: list[ChatMessageModel] | None) -> list[dict] | None:
    if not history:
        return None
    return [{"role": m.role, "content": m.content} for m in history]


def _safe_classify(question: str) -> QueryAnalysis:
    """Always returns a valid QueryAnalysis, never raises."""
    try:
        return classify_query(question)
    except Exception as e:
        print(f"[Query] Classifier failed, using default: {e}")
        return QueryAnalysis(
            intent="single_source", source_types=["any"], topics=[],
            ipc_sections=[], time_filter=None, language_hint="en",
            requires_compare=False, requires_summary=False, source_names=[]
        )


def _do_retrieve(question: str, req_source_ids: list[str] | None, analysis: QueryAnalysis) -> MultiSourceResult:
    """
    THE RETRIEVAL ROUTER.
    Priority:
      1. User explicitly selected sources → use retrieve_multi_selected (CORE FEATURE)
      2. Otherwise → let classifier intent decide
    """
    if req_source_ids and len(req_source_ids) > 0:
        if len(req_source_ids) == 1:
            # Single explicit source
            return retrieve_single_source(question, source_ids=req_source_ids)
        else:
            # MULTI-SOURCE CONSOLIDATION — the core product feature
            return retrieve_multi_selected(question, source_ids=req_source_ids)
    else:
        # No manual selection — let classifier decide
        return multi_retrieve(question, analysis)


def _ensure_conversation(cursor, conv_id: str | None, question: str) -> str:
    if conv_id:
        return conv_id
    new_id = str(uuid.uuid4())
    title = question[:60] + ("..." if len(question) > 60 else "")
    cursor.execute("INSERT INTO conversations (id, title) VALUES (%s, %s)", (new_id, title))
    return new_id


def _save_to_db(chat_id: str, conv_id: str, question: str, answer: str, source_ids_used: list[str]) -> None:
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO chat_history (id, question, answer, sources_used, conversation_id) VALUES (%s, %s, %s, %s, %s)",
                (chat_id, question, answer, json.dumps(source_ids_used), conv_id)
            )
            cursor.execute("UPDATE conversations SET updated_at = NOW() WHERE id = %s", (conv_id,))
            conn.commit()
            print(f"[Query] Saved chat {chat_id[:8]} to conv {conv_id[:8]}")
    except Exception as e:
        print(f"[Query] DB save warning: {e}")


def _pre_create_conv(conv_id: str | None, question: str) -> str:
    """Pre-create a conversation row before streaming starts so meta event can carry real ID."""
    if conv_id:
        return conv_id
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            new_id = _ensure_conversation(cursor, None, question)
            conn.commit()
            return new_id
    except Exception as e:
        print(f"[Query] Pre-create conv warning: {e}")
        return str(uuid.uuid4())


def _format_chunks_out(chunks: list) -> list[dict]:
    return [
        {
            "rank": i + 1,
            "chunkId": c.chunk_id,
            "sourceId": c.source_id,
            "sourceType": c.source_type,
            "sourceTitle": c.source_title,
            "text": c.chunk_text,
            "score": round(c.score, 4),
            "pageNumber": c.page_number,
            "timestampS": c.timestamp_s,
            "urlRef": c.url_ref,
            "language": c.language,
        }
        for i, c in enumerate(chunks)
    ]


def _format_citations_out(citations: list) -> list[dict]:
    return [
        {
            "sourceId": c.source_id,
            "sourceType": c.source_type,
            "sourceTitle": c.source_title,
            "reference": c.reference,
            "snippet": c.snippet,
            "score": round(c.score, 4),
        }
        for c in citations
    ]


# ── /query — standard non-streaming ──────────────────────────────────────────

@router.post("/query")
def query(req: QueryRequest):
    if not req.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty.")

    history = _history_to_dicts(req.history)
    enriched_question, image_context_block = enrich_query_with_image_context(
        req.question, image_id=req.image_id, include_recent=req.include_images
    )

    analysis = _safe_classify(enriched_question)

    try:
        multi_result = _do_retrieve(enriched_question, req.source_ids, analysis)
        chunks = multi_result.all_chunks
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Retrieval error: {str(e)}")

    if not chunks:
        return {
            "chatId": str(uuid.uuid4()), "conversationId": req.conversation_id,
            "answer": "No relevant information found in the selected sources. Please check that documents have been uploaded and try a different question.",
            "citations": [], "retrievedChunks": [], "query_intent": analysis.intent, "imageContextUsed": False
        }

    augmented_history = list(history) if history else []
    if image_context_block:
        augmented_history = [{"role": "system", "content": image_context_block}] + augmented_history

    try:
        result = generate_multi_answer(enriched_question, multi_result, history=augmented_history)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Generation error: {str(e)}")

    chat_id = str(uuid.uuid4())
    source_ids_used = list({c.source_id for c in chunks})

    conv_id = req.conversation_id or ""
    if not conv_id:
        try:
            with get_connection() as conn:
                cursor = conn.cursor()
                conv_id = _ensure_conversation(cursor, None, req.question)
                conn.commit()
        except Exception as e:
            print(f"[Query] Conv create warning: {e}")

    _save_to_db(chat_id, conv_id, req.question, result.answer, source_ids_used)

    return {
        "chatId": chat_id, "conversationId": conv_id,
        "answer": result.answer,
        "citations": _format_citations_out(result.citations),
        "retrievedChunks": _format_chunks_out(result.chunks),
        "query_intent": analysis.intent,
        "imageContextUsed": bool(image_context_block),
    }


# ── /query-stream — SSE streaming (PRIMARY PATH) ─────────────────────────────

@router.post("/query-stream")
def query_stream(req: QueryRequest):
    if not req.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty.")

    history = _history_to_dicts(req.history)
    enriched_question, image_context_block = enrich_query_with_image_context(
        req.question, image_id=req.image_id, include_recent=req.include_images
    )

    # 1. Classify
    analysis = _safe_classify(enriched_question)

    # 2. Retrieve — uses source_ids if provided
    try:
        multi_result = _do_retrieve(enriched_question, req.source_ids, analysis)
        chunks = multi_result.all_chunks
        print(f"[QueryStream] Retrieved {len(chunks)} chunks from {multi_result.source_count} sources")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Retrieval error: {str(e)}")

    # 3. Pre-create conversation so meta event has a real conv_id
    chat_id = str(uuid.uuid4())
    conv_id = _pre_create_conv(req.conversation_id, req.question)

    # 4. Build meta payload (sent immediately before first token)
    citations_out = _format_citations_out(_build_citations(chunks))
    chunks_out = _format_chunks_out(chunks)

    # 5. Build augmented history
    augmented_history = list(history) if history else []
    if image_context_block:
        augmented_history = [{"role": "system", "content": image_context_block}] + augmented_history

    def event_stream():
        # ── Meta event: sent first so UI populates sources panel immediately ──
        yield f"data: {json.dumps({'type': 'meta', 'chatId': chat_id, 'conversationId': conv_id, 'citations': citations_out, 'retrievedChunks': chunks_out, 'sourceCount': multi_result.source_count})}\n\n"

        # ── Empty result ─────────────────────────────────────────────────────
        if not chunks:
            yield f"data: {json.dumps({'type': 'token', 'content': 'No relevant information found in the selected sources. Please check that documents have been uploaded and try a different question.'})}\n\n"
            yield f"data: {json.dumps({'type': 'done'})}\n\n"
            return

        # ── Token stream ─────────────────────────────────────────────────────
        collected = []
        try:
            for token in generate_answer_stream(enriched_question, chunks, history=augmented_history, llm_provider=req.llm_provider):
                collected.append(token)
                yield f"data: {json.dumps({'type': 'token', 'content': token})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
            return

        # ── Done event ────────────────────────────────────────────────────────
        yield f"data: {json.dumps({'type': 'done'})}\n\n"

        # ── Persist to DB after stream ────────────────────────────────────────
        full_answer = "".join(collected).strip()
        source_ids_used = list({c.source_id for c in chunks})
        _save_to_db(chat_id, conv_id, req.question, full_answer, source_ids_used)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
    )


# ── /query/debug — Diagnostic ─────────────────────────────────────────────────

@router.get("/query/debug")
def query_debug(question: str = "test query"):
    """GET /query/debug?question=... — trace FAISS + MySQL pipeline."""
    from backend.ingestion.embedder import embed_query
    from backend.vectorstore.faiss_store import search_vectors, get_stats
    import os

    results = {"question": question, "faiss_stats": get_stats(), "steps": []}

    try:
        results["steps"].append("1. Embedding query...")
        vec = embed_query(question)

        results["steps"].append("2. Searching FAISS...")
        raw_hits = search_vectors(vec, top_k=5)
        results["faiss_hits"] = raw_hits

        if not raw_hits:
            results["steps"].append("WARNING: FAISS returned 0 hits.")
            return results

        results["steps"].append(f"3. Querying MySQL for {len(raw_hits)} IDs...")
        chunk_ids = [h["chunk_id"] for h in raw_hits]
        placeholders = ", ".join(["%s"] * len(chunk_ids))
        with get_connection() as conn:
            cursor = conn.cursor(dictionary=True)
            cursor.execute(f"SELECT id, source_id, chunk_text FROM chunks WHERE id IN ({placeholders})", chunk_ids)
            db_rows = cursor.fetchall()
            for r in db_rows:
                r["snippet"] = (r.get("chunk_text") or "")[:100] + "..."
                r.pop("chunk_text", None)
            results["db_rows"] = db_rows
            results["steps"].append(f"Found {len(db_rows)} matching rows in DB.")

    except Exception as e:
        results["error"] = str(e)

    return results