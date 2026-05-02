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


def _build_messages(
    question     : str,
    chunks       : list[RetrievedChunk],
    history      : list[ChatMessage] | None = None,
    image_context: str | None = None,
) -> list[dict]:
    """
    Build the full messages array sent to Groq's chat completions API.

    Structure sent to Groq:
        [
          {"role": "system",    "content": <RAG instructions + retrieved context>},
          {"role": "user",      "content": <history turn 1 question>},
          {"role": "assistant", "content": <history turn 1 answer>},
          {"role": "user",      "content": <history turn 2 question>},
          {"role": "assistant", "content": <history turn 2 answer>},
          {"role": "user",      "content": <current question>},   ← always last
        ]

    Why put context in the system message?
        The system message is read first and governs the entire conversation.
        Putting retrieved context here means every turn — including follow-ups
        like "Can you expand on that?" — has access to the same source chunks.

    Why include chat history?
        Without history, follow-up questions like "What did you mean by that?"
        have no referent. The model needs prior turns to resolve references.

    History cap (MAX_HISTORY_TURNS = 3):
        We keep the last 3 user+assistant pairs (= 6 messages).
        This keeps the context window usage predictable and well within
        llama3-8b-8192's 8192 token limit. Older turns are dropped.

    Args:
        question : the current user question
        chunks   : retrieved chunks for this turn
        history  : previous {"role", "content"} turns, oldest first. Can be None.

    Returns:
        list of message dicts ready for Groq chat completions
    """
    MAX_HISTORY_TURNS = 3   # last 3 turns = last 6 messages

    # ── Build context block ───────────────────────────────────────────────────
    context_parts = []
    for i, chunk in enumerate(chunks, start=1):
        ref    = _build_reference(chunk)
        header = f"[{i}] Source: {chunk.source_title}"
        if ref:
            header += f" ({ref})"
        context_parts.append(f"{header}\n{chunk.chunk_text}")

    context = "\n\n".join(context_parts)

    # ── System message: instructions + context ────────────────────────────────
    system_content = f"""You are a helpful AI assistant. Answer questions using ONLY the context provided below.
If the answer is not in the context, say "I don't have enough information to answer this question."
Always be specific and cite which source your answer comes from.
When answering follow-up questions, use the conversation history to understand what the user is referring to.

RETRIEVED CONTEXT:
{context}"""

    if image_context:
        system_content = f"{system_content}\n\n{image_context}"

    messages: list[dict] = [
        {"role": "system", "content": system_content}
    ]

    # ── Append capped chat history ────────────────────────────────────────────
    if history:
        # Each turn = 1 user msg + 1 assistant msg = 2 entries
        recent = history[-(MAX_HISTORY_TURNS * 2):]
        for msg in recent:
            if msg.get("role") in ("user", "assistant") and msg.get("content"):
                messages.append({
                    "role"   : msg["role"],
                    "content": str(msg["content"]),
                })

    # ── Current question is always the final user message ────────────────────
    messages.append({"role": "user", "content": question})

    return messages


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
    chunks       : list[RetrievedChunk],
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
    if not chunks:
        yield "I don't have any relevant information to answer this question. Please upload some documents first."
        return

    messages = _build_messages(question, chunks, history, image_context=image_context)
    print(f"[Generator] Streaming | model={GROQ_MODEL} | "
          f"history_turns={len(history) if history else 0} | "
          f"total_messages={len(messages)}")

    if llm_provider == "huggingface":
        # HF API doesn't robustly support SSE without dedicated endpoints.
        # We will block, fetch the whole answer, and yield it as one token.
        print(f"[Generator] Using HF API for {HF_LEGAL_MODEL_ID}")
        answer = _call_hf_api(messages)
        yield answer
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
    chunks       : list[RetrievedChunk],
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
    if not chunks:
        return GeneratedAnswer(
            answer    = "I don't have any relevant information to answer this question. Please upload some documents first.",
            citations = [],
            chunks    = []
        )

    # ── Step 1: Build messages with history ───────────────────────────────────
    messages = _build_messages(question, chunks, history, image_context=image_context)
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
    citations = _build_citations(chunks)

    return GeneratedAnswer(
        answer    = answer,
        citations = citations,
        chunks    = chunks
    )