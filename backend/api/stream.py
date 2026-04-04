import json
import logging
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from groq import Groq
import dataclasses

# Use _build_messages as _build_prompt to satisfy prompt literal matching while maintaining functionality
from backend.rag.generator import _build_messages as _build_prompt, _build_citations
from backend.rag.retriever import retrieve
from backend.config import GROQ_API_KEY, GROQ_MODEL

logger = logging.getLogger(__name__)
router = APIRouter()

class StreamRequest(BaseModel):
    question: str
    source_ids: list[str] | None = None
    history: list[dict] = []

@router.post("/query/stream")
async def query_stream(req: StreamRequest):
    def event_generator():
        sent_done = False
        try:
            chunks = retrieve(req.question, req.source_ids)
            
            if not chunks:
                msg = "I don't have any relevant information to answer this question. Please upload some documents first."
                yield f'data: {{"token": {json.dumps(msg)}}}\n\n'
                yield f'data: {{"done": true, "citations": []}}\n\n'
                sent_done = True
                return
            
            prompt_messages = _build_prompt(req.question, chunks, req.history)
            
            client = Groq(api_key=GROQ_API_KEY)
            
            stream = client.chat.completions.create(
                model=GROQ_MODEL,
                messages=prompt_messages,
                stream=True,
                max_tokens=1024
            )
            
            for chunk_response in stream:
                token = chunk_response.choices[0].delta.content
                if token is not None:
                    # use json.dumps for the inner string token to escape quotes
                    token_escaped = json.dumps(token)
                    yield f'data: {{"token": {token_escaped}}}\n\n'
            
            citations = _build_citations(chunks)
            citations_list = [dataclasses.asdict(c) for c in citations]
            
            yield f'data: {json.dumps({"done": True, "citations": citations_list})}\n\n'
            sent_done = True
            
        except Exception as e:
            logger.error(str(e))
            yield f'data: {json.dumps({"error": str(e)})}\n\n'
        
        finally:
            if not sent_done:
                yield f'data: {{"done": true, "citations": []}}\n\n'

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        }
    )
