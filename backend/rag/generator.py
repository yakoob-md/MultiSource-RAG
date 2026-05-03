from groq import Groq
import requests
from dataclasses import dataclass
from typing import Generator
from backend.config import GROQ_API_KEY, GROQ_MODEL, GROQ_TIMEOUT, HF_API_KEY, HF_LEGAL_MODEL_ID
from backend.rag.retriever import RetrievedChunk
from backend.core.llm_provider import llm_provider


# ── Chat history type ─────────────────────────────────────────────────────────
# A single turn in the conversation history.
# role  : "user" or "assistant"
# content: the message text
ChatMessage = dict  # {"role": "user"|"assistant", "content": str}


@dataclass
class Citation:
    """
    One source citation shown under the AI answer.

    Fields:
        source_id   : UUID of the source
        source_type : "pdf" | "url" | "youtube"
        source_title: human readable name
        reference   : page number, timestamp, or URL
        snippet     : short preview of the chunk text
        score       : similarity score
    """
    source_id   : str
    source_type : str
    source_title: str
    reference   : str
    snippet     : str
    score       : float


@dataclass
class GeneratedAnswer:
    """
    The complete response returned to the frontend (non-streaming path).

    Fields:
        answer    : the LLM generated answer text
        citations : list of Citation objects (up to 5)
        chunks    : all retrieved chunks (for the right panel in AskAI)
    """
    answer   : str
    citations: list[Citation]
    chunks   : list[RetrievedChunk]


def _build_reference(chunk: RetrievedChunk) -> str:
    """
    Build a human readable reference string for a chunk.

    Examples:
        PDF     → "page 3"
        URL     → "https://example.com"
        YouTube → "at 2:34 (https://youtube.com/watch?v=...&t=154s)"
    """
    if chunk.source_type == "pdf" and chunk.page_number:
        return f"page {chunk.page_number}"
    elif chunk.source_type == "youtube" and chunk.timestamp_s is not None:
        mins = chunk.timestamp_s // 60
        secs = chunk.timestamp_s % 60
        time_str = f"{mins}:{secs:02d}"
        url  = chunk.url_ref or ""
        return f"at {time_str} ({url})"
    elif chunk.source_type == "url" and chunk.url_ref:
        return chunk.url_ref
    return ""


from backend.rag.prompts import build_single_source_prompt, build_comparison_prompt, build_synthesis_prompt
from backend.rag.multi_retriever import MultiSourceResult

def _build_messages_rich(
    question     : str,
    result       : MultiSourceResult,
    history      : list[ChatMessage] | None = None,
    image_context: str | None = None,
    is_legal     : bool = False,
) -> list[dict]:
    """Select the best prompt builder based on query intent."""
    if result.query_intent == "comparison":
        return build_comparison_prompt(question, result, history, image_context, is_legal=is_legal)
    elif result.query_intent == "synthesis":
        return build_synthesis_prompt(question, result, history, image_context, is_legal=is_legal)
    else:
        return build_single_source_prompt(question, result, history, image_context, is_legal=is_legal)


def _get_groq_client() -> Groq:
    """
    Create and return a configured Groq client.
    Raises a clear error if the API key is missing.
    """
    if not GROQ_API_KEY:
        raise ValueError(
            "GROQ_API_KEY is not set. "
            "Get a free key at https://console.groq.com and set it as an "
            "environment variable: set GROQ_API_KEY=gsk_..."
        )
    return Groq(api_key=GROQ_API_KEY)


def _call_provider(messages: list[dict], llm_provider_name: str | None) -> str:
    """Call the centralized LLM provider."""
    mode = "finetuned" if llm_provider_name == "huggingface" else "base"
    return llm_provider.generate(messages, mode=mode)


def _build_citations(chunks: list[RetrievedChunk]) -> list[Citation]:
    """
    Build citation list from top 5 chunks, one citation per unique source.
    Shared by both streaming and non-streaming paths.
    """
    citations    = []
    seen_sources = set()

    for chunk in chunks[:5]:
        if chunk.source_id in seen_sources:
            continue
        seen_sources.add(chunk.source_id)

        citations.append(Citation(
            source_id    = chunk.source_id,
            source_type  = chunk.source_type,
            source_title = chunk.source_title,
            reference    = _build_reference(chunk),
            snippet      = chunk.chunk_text[:150] + "...",
            score        = chunk.score,
        ))

    return citations


# ── Streaming path ────────────────────────────────────────────────────────────

def generate_answer_stream(
    question     : str,
    multi_result : MultiSourceResult,
    history      : list[ChatMessage] | None = None,
    image_context: str | None = None,
    provider_name: str | None = "groq",
    is_legal     : bool = False,
) -> Generator[str, None, None]:
    """
    Streaming answer generation with chat history support.

    Yields text tokens as they arrive from Groq.
    Used by the /query-stream SSE endpoint.

    Args:
        question : the current user question
        chunks   : retrieved chunks from the retriever
        history  : previous conversation turns (oldest first), or None

    Yields:
        str tokens (partial answer text)
    """
    if not multi_result.all_chunks:
        yield "I don't have any relevant information to answer this question. Please upload some documents first."
        return

    is_legal = is_legal or (provider_name == "huggingface")
    messages = _build_messages_rich(question, multi_result, history, image_context=image_context, is_legal=is_legal)
    
    # ── Option 1: Groq (Native Streaming) ─────────────────────────────────────
    if provider_name != "huggingface":
        client = _get_groq_client()
        stream = client.chat.completions.create(
            model    = GROQ_MODEL,
            messages = messages,
            stream   = True,
            timeout  = GROQ_TIMEOUT,
        )
        for chunk_response in stream:
            token = chunk_response.choices[0].delta.content
            if token is not None:
                yield token
        return

    # ── Option 2: Fine-tuned (Kaggle/Local) ───────────────────────────────────
    # We use the centralized provider. Since it's currently non-streaming,
    # we simulate streaming for a better UI experience.
    try:
        answer = llm_provider.generate(messages, mode="finetuned")
        words = answer.split(" ")
        for i, word in enumerate(words):
            yield word + (" " if i < len(words) - 1 else "")
            # Micro-sleep to prevent UI from freezing
            import time
            time.sleep(0.01)
    except Exception as e:
        yield f"Generation error: {str(e)}"


# ── Non-streaming path ────────────────────────────────────────────────────────

def generate_answer(
    question     : str,
    multi_result : MultiSourceResult,
    history      : list[ChatMessage] | None = None,
    image_context: str | None = None,
    llm_provider : str | None = "groq",
    is_legal     : bool = False,
) -> GeneratedAnswer:
    """
    Non-streaming answer generation with chat history support.

    Returns a complete GeneratedAnswer object.
    Used by the standard /query endpoint.

    Args:
        question : the current user question
        chunks   : retrieved chunks from the retriever
        history  : previous conversation turns (oldest first), or None

    Returns:
        GeneratedAnswer with answer text, citations, and chunks
    """
    if not multi_result.all_chunks:
        return GeneratedAnswer(
            answer    = "I don't have any relevant information to answer this question. Please upload some documents first.",
            citations = [],
            chunks    = []
        )

    # ── Step 1: Build messages with history ───────────────────────────────────
    is_legal = is_legal or (llm_provider == "huggingface")
    messages = _build_messages_rich(question, multi_result, history, image_context=image_context, is_legal=is_legal)
    print(f"[Generator] Sending | model={GROQ_MODEL} | "
          f"history_turns={len(history) if history else 0} | "
          f"total_messages={len(messages)}")

    # ── Step 2: Call Centralized Provider ──────────────────────────────────────
    try:
        mode = "finetuned" if provider_name == "huggingface" else "base"
        answer = llm_provider.generate(messages, mode=mode)
        print(f"[Generator] Done | {len(answer)} chars")

    except ValueError:
        raise
    except Exception as e:
        raise RuntimeError(f"Groq API error: {e}") from e

    # ── Step 3: Build citations ───────────────────────────────────────────────
    citations = _build_citations(multi_result.all_chunks)

    return GeneratedAnswer(
        answer    = answer,
        citations = citations,
        chunks    = multi_result.all_chunks
    )