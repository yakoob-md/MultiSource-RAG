# backend/api/stream.py — KEY FIX: add retrievedChunks to done event

import json
import logging
import asyncio
import dataclasses
from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from groq import Groq

from backend.rag.generator import _build_messages as _build_prompt, _build_citations
from backend.rag.retriever import retrieve, RetrievedChunk
from backend.config import GROQ_API_KEY, GROQ_MODEL

logger = logging.getLogger(__name__)
router = APIRouter()

SCORE_THRESHOLD = -5.0  # Reranker scores below this = irrelevant, drop them

class StreamRequest(BaseModel):
    question: str
    source_ids: list[str] | None = None
    history: list[dict] = []

def _chunk_to_dict(chunk: RetrievedChunk) -> dict:
    """Serialize a RetrievedChunk for the frontend."""
    return {
        "chunkId"    : chunk.chunk_id,
        "sourceId"   : chunk.source_id,
        "sourceType" : chunk.source_type,
        "sourceTitle": chunk.source_title,
        "text"       : chunk.chunk_text,
        "score"      : round(chunk.score, 4),
        "pageNumber" : chunk.page_number,
        "timestampS" : chunk.timestamp_s,
        "urlRef"     : chunk.url_ref,
        "language"   : chunk.language,
    }

@router.post("/query/stream")
async def query_stream(req: StreamRequest, request: Request):
    async def event_generator():
        sent_done = False
        try:
            # Wait for models if warming up
            if hasattr(request.app.state, 'models_ready') and \
               not request.app.state.models_ready.is_set():
                msg = "⏳ *Warming up models... please wait ~15 seconds.*\n\n"
                yield f'data: {{"token": {json.dumps(msg)}}}\n\n'
                while not request.app.state.models_ready.is_set():
                    yield f'data: {{"token": ""}}\n\n'
                    try:
                        await asyncio.wait_for(
                            request.app.state.models_ready.wait(), timeout=1.0
                        )
                    except asyncio.TimeoutError:
                        continue

            # Retrieve chunks
            chunks = await asyncio.to_thread(retrieve, req.question, req.source_ids)

            # Apply score threshold to reduce hallucination
            if chunks:
                chunks = [c for c in chunks if c.score >= SCORE_THRESHOLD]

            if not chunks:
                msg = "I don't have relevant information to answer this. Please upload documents first."
                yield f'data: {{"token": {json.dumps(msg)}}}\n\n'
                yield f'data: {{"done": true, "citations": [], "retrievedChunks": []}}\n\n'
                sent_done = True
                return

            prompt_messages = _build_prompt(req.question, chunks, req.history)

            def run_groq():
                client = Groq(api_key=GROQ_API_KEY)
                return client.chat.completions.create(
                    model=GROQ_MODEL,
                    messages=prompt_messages,
                    stream=True,
                    max_tokens=1024
                )

            stream = await asyncio.to_thread(run_groq)

            for chunk_response in stream:
                token = chunk_response.choices[0].delta.content
                if token is not None:
                    yield f'data: {{"token": {json.dumps(token)}}}\n\n'
                    await asyncio.sleep(0)

            # Build citations and chunks for frontend panels
            citations = _build_citations(chunks)
            citations_list = [dataclasses.asdict(c) for c in citations]
            chunks_list = [_chunk_to_dict(c) for c in chunks]

            # FIX: Include retrievedChunks in done payload so right panel populates
            yield f'data: {json.dumps({"done": True, "citations": citations_list, "retrievedChunks": chunks_list})}\n\n'
            sent_done = True

        except Exception as e:
            logger.error(f"[Stream] Error: {e}")
            yield f'data: {json.dumps({"error": str(e)})}\n\n'
        finally:
            if not sent_done:
                yield f'data: {{"done": true, "citations": [], "retrievedChunks": []}}\n\n'

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control"    : "no-cache",
            "X-Accel-Buffering": "no",
            "Connection"       : "keep-alive",
        }
    )