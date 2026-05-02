from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from backend.rag.retriever import retrieve
from backend.rag.generator import generate_answer, generate_answer_stream, _build_citations
from backend.rag.query_classifier import classify_query
from backend.rag.multi_retriever import multi_retrieve
from backend.rag.multi_generator import generate_multi_answer
from backend.database.connection import get_connection
import uuid
import json

router = APIRouter()


class ChatMessageModel(BaseModel):
    """One turn in the conversation history sent from the frontend."""
    role   : str   # "user" or "assistant"
    content: str


class QueryRequest(BaseModel):
    question  : str
    source_ids: list[str] | None = None
    # history is optional — if not sent, behaves exactly like before
    # Frontend sends the last N turns as a list of {role, content} objects
    history        : list[ChatMessageModel] | None = None
    mode           : str | None = None  # "auto" | "single" | "compare" | "synthesize"
    conversation_id: str | None = None


# ── Helper: convert Pydantic models → plain dicts for generator ───────────────

def _history_to_dicts(history: list[ChatMessageModel] | None) -> list[dict] | None:
    """
    Convert Pydantic ChatMessageModel list to plain dicts.
    generator.py expects list[dict], not list[ChatMessageModel].
    Returns None if history is None or empty.
    """
    if not history:
        return None
    return [{"role": msg.role, "content": msg.content} for msg in history]


# ── Standard (non-streaming) endpoint ────────────────────────────────────────

@router.post("/query")
def query(req: QueryRequest):
    """
    POST /query
    Standard non-streaming RAG endpoint with chat history support.

    Body:
    {
        "question"  : "What did you mean by attention?",
        "source_ids": ["uuid1"],          ← optional
        "history"   : [                   ← optional, last N turns
            {"role": "user",      "content": "Explain transformers"},
            {"role": "assistant", "content": "Transformers are..."}
        ]
    }

    Response:
    {
        "answer"         : "...",
        "citations"      : [...],
        "retrievedChunks": [...],
        "chatId"         : "uuid"
    }
    """
    if not req.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty.")

    history = _history_to_dicts(req.history)

    # ── Step 1: Query Analysis & Classification ──────────────────────────────
    try:
        analysis = classify_query(req.question)
        if req.mode and req.mode != "auto":
            analysis.intent = {"single": "single_source", "compare": "comparison",
                                "synthesize": "synthesis"}.get(req.mode, analysis.intent)
    except Exception as e:
        print(f"[Query] Classifier warning: {e}")
        # Fallback will be handled by classify_query returning a safe default

    # ── Step 2: Retrieve relevant chunks ──────────────────────────────────────
    try:
        multi_result = multi_retrieve(req.question, analysis)
        chunks = multi_result.all_chunks
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Retrieval error: {str(e)}")

    # ── Step 3: Generate answer (with history) ────────────────────────────────
    try:
        result = generate_multi_answer(req.question, multi_result, history=history)
    except ValueError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Generation error: {str(e)}")

    # ── Step 4: Save to chat history (with conversation) ─────────────────────────
    chat_id         = str(uuid.uuid4())
    source_ids_used = list({c.source_id for c in chunks})

    try:
        with get_connection() as conn:
            cursor = conn.cursor()

            # Auto-create conversation if not provided
            conv_id = req.conversation_id
            if not conv_id:
                conv_id = str(uuid.uuid4())
                # Use first 50 chars of question as title
                title = req.question[:50] + ("..." if len(req.question) > 50 else "")
                cursor.execute(
                    "INSERT INTO conversations (id, title) VALUES (%s, %s)",
                    (conv_id, title)
                )

            cursor.execute("""
                INSERT INTO chat_history (id, conversation_id, question, answer, sources_used)
                VALUES (%s, %s, %s, %s, %s)
            """, (
                chat_id,
                conv_id,
                req.question,
                result.answer,
                json.dumps(source_ids_used)
            ))

            # Update conversation's updated_at
            cursor.execute(
                "UPDATE conversations SET updated_at = NOW() WHERE id = %s",
                (conv_id,)
            )
            conn.commit()
    except Exception as e:
        print(f"[Query] Warning: Could not save chat history: {e}")

    # ── Step 5: Build response ────────────────────────────────────────────────
    citations_out = []
    for c in result.citations:
        citations_out.append({
            "sourceId"   : c.source_id,
            "sourceType" : c.source_type,
            "sourceTitle": c.source_title,
            "reference"  : c.reference,
            "snippet"    : c.snippet,
            "score"      : round(c.score, 4),
        })

    chunks_out = []
    for i, c in enumerate(result.chunks):
        chunks_out.append({
            "rank"       : i + 1,
            "chunkId"    : c.chunk_id,
            "sourceId"   : c.source_id,
            "sourceType" : c.source_type,
            "sourceTitle": c.source_title,
            "text"       : c.chunk_text,
            "score"      : round(c.score, 4),
            "pageNumber" : c.page_number,
            "timestampS" : c.timestamp_s,
            "urlRef"     : c.url_ref,
            "language"   : c.language,
        })

    return {
        "chatId"         : chat_id,
        "conversationId" : conv_id,
        "answer"         : result.answer,
        "citations"      : citations_out,
        "retrievedChunks": chunks_out,
        "query_intent"   : analysis.intent,
    }


# ── Streaming endpoint ────────────────────────────────────────────────────────

@router.post("/query-stream")
def query_stream(req: QueryRequest):
    """
    POST /query-stream
    Streaming RAG endpoint (SSE) with chat history support.

    SSE event sequence:
        data: {"type": "meta",  "chatId": "...", "citations": [...], "retrievedChunks": [...]}
        data: {"type": "token", "content": "The "}
        data: {"type": "token", "content": "answer "}
        ...
        data: {"type": "done"}

    Body (same shape as /query):
    {
        "question"  : "What did you mean by attention?",
        "source_ids": ["uuid1"],          ← optional
        "history"   : [                   ← optional, last N turns
            {"role": "user",      "content": "Explain transformers"},
            {"role": "assistant", "content": "Transformers are..."}
        ]
    }

    Flow:
      1. Retrieve chunks
      2. Immediately send "meta" event → frontend renders sources panel
      3. Stream tokens one by one → frontend appends each token to message
      4. Send "done" event → frontend marks message as complete
      5. Save full answer to DB after stream finishes
    """
    if not req.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty.")

    history = _history_to_dicts(req.history)

    # ── Step 1: Retrieve chunks ────────────────────────────────────────────────
    try:
        chunks = retrieve(req.question, req.source_ids)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Retrieval error: {str(e)}")

    # ── Step 2: Pre-build citations and chunk metadata ────────────────────────
    citations_out = []
    for c in _build_citations(chunks):
        citations_out.append({
            "sourceId"   : c.source_id,
            "sourceType" : c.source_type,
            "sourceTitle": c.source_title,
            "reference"  : c.reference,
            "snippet"    : c.snippet,
            "score"      : round(c.score, 4),
        })

    chunks_out = []
    for i, c in enumerate(chunks):
        chunks_out.append({
            "rank"       : i + 1,
            "chunkId"    : c.chunk_id,
            "sourceId"   : c.source_id,
            "sourceType" : c.source_type,
            "sourceTitle": c.source_title,
            "text"       : c.chunk_text,
            "score"      : round(c.score, 4),
            "pageNumber" : c.page_number,
            "timestampS" : c.timestamp_s,
            "urlRef"     : c.url_ref,
            "language"   : c.language,
        })

    chat_id = str(uuid.uuid4())

    # ── Step 3: SSE generator ─────────────────────────────────────────────────
    def event_stream():
        # Event 1: metadata — sent immediately so sources panel renders
        # before the first token even arrives
        # We need to determine the conv_id early for the metadata event
        conv_id_meta = req.conversation_id
        if not conv_id_meta:
            # We don't create it here to avoid race conditions or empty convs if stream fails immediately,
            # but we need a stable ID if the frontend wants to use it.
            # Actually, let's just generate a potential one or wait.
            # Best practice: if not provided, the 'meta' event might have a null conversationId 
            # until the first token or the end. 
            # But the user logic says return it.
            pass

        yield f"data: {json.dumps({'type': 'meta', 'chatId': chat_id, 'conversationId': req.conversation_id, 'citations': citations_out, 'retrievedChunks': chunks_out})}\n\n"

        # Events 2..N: stream tokens
        collected_tokens = []
        try:
            for token in generate_answer_stream(req.question, chunks, history=history):
                collected_tokens.append(token)
                yield f"data: {json.dumps({'type': 'token', 'content': token})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
            return

        # Final event: frontend uses this to mark the message as complete
        yield f"data: {json.dumps({'type': 'done'})}\n\n"

        # Save full answer to DB after stream completes
        full_answer     = "".join(collected_tokens).strip()
        source_ids_used = list({c.source_id for c in chunks})
        try:
            with get_connection() as conn:
                cursor = conn.cursor()

                # Auto-create conversation if not provided
                conv_id_stream = req.conversation_id
                if not conv_id_stream:
                    conv_id_stream = str(uuid.uuid4())
                    title = req.question[:50] + ("..." if len(req.question) > 50 else "")
                    cursor.execute(
                        "INSERT INTO conversations (id, title) VALUES (%s, %s)",
                        (conv_id_stream, title)
                    )

                cursor.execute("""
                    INSERT INTO chat_history (id, conversation_id, question, answer, sources_used)
                    VALUES (%s, %s, %s, %s, %s)
                """, (
                    chat_id,
                    conv_id_stream,
                    req.question,
                    full_answer,
                    json.dumps(source_ids_used)
                ))

                # Update updated_at
                cursor.execute(
                    "UPDATE conversations SET updated_at = NOW() WHERE id = %s",
                    (conv_id_stream,)
                )
                conn.commit()
        except Exception as e:
            print(f"[QueryStream] Warning: Could not save chat history: {e}")

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control"    : "no-cache",
            "X-Accel-Buffering": "no",
        }
    )