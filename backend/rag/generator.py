from groq import Groq
import requests
from dataclasses import dataclass
from typing import Generator
from backend.config import GROQ_API_KEY, GROQ_MODEL, GROQ_TIMEOUT, HF_API_KEY, HF_LEGAL_MODEL_ID
from backend.rag.retriever import RetrievedChunk


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


def _call_hf_api(messages: list[dict]) -> str:
    """Call Hugging Face Inference API for the fine-tuned model."""
    if not HF_API_KEY or not HF_LEGAL_MODEL_ID:
        raise ValueError("HF_API_KEY or HF_LEGAL_MODEL_ID not set in config.")
        
    api_url = f"https://api-inference.huggingface.co/models/{HF_LEGAL_MODEL_ID}"
    headers = {"Authorization": f"Bearer {HF_API_KEY}"}
    
    # Convert chat history to a single string prompt (HF Inference API often expects string inputs for causal LM)
    # Basic chat template approximation
    prompt = ""
    for m in messages:
        if m["role"] == "system":
            prompt += f"<<SYS>>\n{m['content']}\n<</SYS>>\n\n"
        elif m["role"] == "user":
            prompt += f"[INST] {m['content']} [/INST] "
        elif m["role"] == "assistant":
            prompt += f"{m['content']} </s><s>"
            
    response = requests.post(api_url, headers=headers, json={
        "inputs": prompt,
        "parameters": {"max_new_tokens": 1024, "temperature": 0.3, "return_full_text": False}
    }, timeout=GROQ_TIMEOUT)
    
    if response.status_code == 200:
        res = response.json()
        if isinstance(res, list) and len(res) > 0 and "generated_text" in res[0]:
            return res[0]["generated_text"].strip()
        return str(res)
    else:
        raise RuntimeError(f"HF API Error {response.status_code}: {response.text}")


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
    llm_provider : str | None = "groq",
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

    is_legal = (llm_provider == "huggingface")
    messages = _build_messages_rich(question, multi_result, history, image_context=image_context, is_legal=is_legal)
    print(f"[Generator] Streaming | model={GROQ_MODEL} | "
          f"history_turns={len(history) if history else 0} | "
          f"total_messages={len(messages)}")

    if llm_provider == "huggingface":
        print(f"[Generator] Streaming from HF API: {HF_LEGAL_MODEL_ID}")
        # HF Inference API supports streaming via SSE if we pass stream: true
        api_url = f"https://api-inference.huggingface.co/models/{HF_LEGAL_MODEL_ID}"
        headers = {"Authorization": f"Bearer {HF_API_KEY}"}
        
        # Approximate prompt (same as _call_hf_api)
        prompt = ""
        for m in messages:
            if m["role"] == "system":
                prompt += f"<<SYS>>\n{m['content']}\n<</SYS>>\n\n"
            elif m["role"] == "user":
                prompt += f"[INST] {m['content']} [/INST] "
            elif m["role"] == "assistant":
                prompt += f"{m['content']} </s><s>"

        try:
            import json
            response = requests.post(api_url, headers=headers, json={
                "inputs": prompt,
                "parameters": {"max_new_tokens": 1024, "temperature": 0.3, "return_full_text": False},
                "stream": True
            }, timeout=GROQ_TIMEOUT, stream=True)

            if response.status_code != 200:
                yield f"Error from HF API ({response.status_code}): {response.text}"
                return

            for line in response.iter_lines():
                if line:
                    decoded = line.decode('utf-8')
                    if decoded.startswith('data:'):
                        try:
                            data = json.loads(decoded[5:])
                            token = data.get("token", {}).get("text", "")
                            if token:
                                yield token
                        except:
                            continue
            return
        except Exception as e:
            print(f"[Generator] HF Stream Error: {e}")
            # Fallback to non-stream if stream fails
            answer = _call_hf_api(messages)
            # Simulate streaming for fallback
            import time
            for word in answer.split(" "):
                yield word + " "
                time.sleep(0.02)
            return

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


# ── Non-streaming path ────────────────────────────────────────────────────────

def generate_answer(
    question     : str,
    multi_result : MultiSourceResult,
    history      : list[ChatMessage] | None = None,
    image_context: str | None = None,
    llm_provider : str | None = "groq",
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
    is_legal = (llm_provider == "huggingface")
    messages = _build_messages_rich(question, multi_result, history, image_context=image_context, is_legal=is_legal)
    print(f"[Generator] Sending | model={GROQ_MODEL} | "
          f"history_turns={len(history) if history else 0} | "
          f"total_messages={len(messages)}")

    # ── Step 2: Call Groq or HF ────────────────────────────────────────────────
    try:
        if llm_provider == "huggingface":
            print(f"[Generator] Sending to HF API: {HF_LEGAL_MODEL_ID}")
            answer = _call_hf_api(messages)
        else:
            client = _get_groq_client()

            stream = client.chat.completions.create(
                model    = GROQ_MODEL,
                messages = messages,
                stream   = True,
                timeout  = GROQ_TIMEOUT,
            )

            tokens = []
            for chunk_response in stream:
                token = chunk_response.choices[0].delta.content
                if token is not None:
                    tokens.append(token)

            answer = "".join(tokens).strip()
            
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