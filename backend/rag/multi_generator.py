import json
from groq import Groq
from backend.config import GROQ_API_KEY, GROQ_MODEL, GROQ_TIMEOUT
from backend.rag.generator import GeneratedAnswer, _build_citations, _get_groq_client
from backend.rag.multi_retriever import MultiSourceResult
from backend.rag.retriever import RetrievedChunk
from backend.core.schemas import UnifiedChunkMetadata
from backend.database.connection import get_connection

def _fetch_unified_metadata(chunk_id: str) -> dict:
    """Fetch unified_metadata for a specific chunk from the database."""
    try:
        with get_connection() as conn:
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT unified_metadata FROM chunks WHERE id = %s", (chunk_id,))
            row = cursor.fetchone()
            if row and row['unified_metadata']:
                # If it's already a dict (mysql-connector does this for JSON), return it
                # Otherwise parse it.
                meta = row['unified_metadata']
                if isinstance(meta, str):
                    return json.loads(meta)
                return meta
    except Exception as e:
        print(f"[MultiGenerator] Error fetching metadata for {chunk_id}: {e}")
    return {}

def _format_chunk_for_prompt(rank: int, chunk: RetrievedChunk) -> str:
    # Try to get unified metadata for better citation
    meta_dict = _fetch_unified_metadata(chunk.chunk_id)
    
    # Extract specific fields as requested
    section_id = meta_dict.get("section_id")
    case_name = meta_dict.get("case_name")
    para_range = meta_dict.get("para_range")
    
    ref_detail = ""
    if section_id:
        ref_detail = f"Section {section_id}"
    elif case_name:
        ref_detail = case_name
    elif para_range:
        ref_detail = f"para {para_range}"
    else:
        # Fallback to page number or timestamp if available
        if chunk.page_number:
            ref_detail = f"page {chunk.page_number}"
        elif chunk.timestamp_s is not None:
            ref_detail = f"at {chunk.timestamp_s}s"

    header = f"[{rank}] {chunk.source_title}"
    if ref_detail:
        header += f" — {ref_detail}"
        
    return f"{header}\n{chunk.chunk_text}"

def build_single_source_prompt(question: str, result: MultiSourceResult, history: list[dict] | None, image_context: str | None = None) -> list[dict]:
    system_prompt = """You are a legal information assistant for Indian law. Answer using ONLY the provided context.
    Structure your answer as:
    ANSWER: [clear explanation]
    LEGAL BASIS: [exact quote from source]
    CITATIONS: [numbered list: Document | Section/Para | Court | Date]
    AMENDMENTS: [any amendments to cited sections]
    Never give legal advice. State only what the law says."""

    context_parts = []
    for i, chunk in enumerate(result.all_chunks, start=1):
        context_parts.append(_format_chunk_for_prompt(i, chunk))
    
    context_block = "\n\n".join(context_parts)
    
    if image_context:
        system_prompt = f"{system_prompt}\n\n{image_context}"

    messages = [
        {"role": "system", "content": f"{system_prompt}\n\nRETRIEVED CONTEXT:\n{context_block}"}
    ]
    
    if history:
        messages.extend(history[-6:]) # Keep last 3 turns
        
    messages.append({"role": "user", "content": question})
    return messages

def build_comparison_prompt(question: str, result: MultiSourceResult, history: list[dict] | None, image_context: str | None = None) -> list[dict]:
    system_prompt = """You are a legal analyst. Compare the provided sources objectively.
    Structure your answer as:
    QUERY: [restate what is being compared]
    SOURCE A — {first source title}:
    [what source A says, with exact quote]
    SOURCE B — {second source title}:
    [what source B says, with exact quote]
    KEY DIFFERENCES:
    [bullet points of substantive differences]
    KEY SIMILARITIES:
    [bullet points of shared principles]
    CITATIONS: [numbered, one per claim]
    Do not take sides. Report what each source states."""

    context_parts = []
    for title, chunks in result.source_groups.items():
        group_context = "\n".join([_format_chunk_for_prompt(i+1, c) for i, c in enumerate(chunks)])
        context_parts.append(f"=== SOURCE: {title} ===\n{group_context}")
    
    context_block = "\n\n".join(context_parts)
    
    # Try to fill placeholders in system prompt if we have at least 2 sources
    titles = list(result.source_groups.keys())
    s_prompt = system_prompt
    if len(titles) >= 2:
        s_prompt = s_prompt.replace("{first source title}", titles[0])
        s_prompt = s_prompt.replace("{second source title}", titles[1])
    
    if image_context:
        s_prompt = f"{s_prompt}\n\n{image_context}"

    messages = [
        {"role": "system", "content": f"{s_prompt}\n\nRETRIEVED CONTEXT:\n{context_block}"}
    ]
    
    if history:
        messages.extend(history[-6:])
        
    messages.append({"role": "user", "content": question})
    return messages

def build_synthesis_prompt(question: str, result: MultiSourceResult, history: list[dict] | None, image_context: str | None = None) -> list[dict]:
    system_prompt = """You are synthesizing information across multiple legal sources.
    Structure your answer as:
    SYNTHESIS:
    [2-3 paragraph summary of common themes and information across sources]
    BY SOURCE:
    {for each source: 2-3 sentence summary of what that source contributes}
    COMMON THEMES: [bullet list]
    DIVERGENCES: [where sources differ, if any]
    CITATIONS: [numbered]"""

    context_parts = []
    for title, chunks in result.source_groups.items():
        # Just use top 2 chunks per source for synthesis to keep context balanced and concise
        group_context = "\n".join([_format_chunk_for_prompt(i+1, c) for i, c in enumerate(chunks[:2])])
        context_parts.append(f"=== SOURCE: {title} ===\n{group_context}")
        
    context_block = "\n\n".join(context_parts)
    
    if image_context:
        system_prompt = f"{system_prompt}\n\n{image_context}"

    messages = [
        {"role": "system", "content": f"{system_prompt}\n\nRETRIEVED CONTEXT:\n{context_block}"}
    ]
    
    if history:
        messages.extend(history[-6:])
        
    messages.append({"role": "user", "content": question})
    return messages

def generate_multi_answer(question: str, result: MultiSourceResult, history: list[dict] | None = None, image_context: str | None = None) -> GeneratedAnswer:
    if not result.all_chunks:
        return GeneratedAnswer(
            answer="I searched your knowledge base but found no relevant information. \n This usually means: (1) no documents have been ingested yet, \n (2) your question doesn't match any uploaded content, or \n (3) the FAISS index is empty. \n Please upload a PDF or website first, then try again.",
            citations=[],
            chunks=[]
        )

    # 1. Select builder
    if result.query_intent == "comparison":
        messages = build_comparison_prompt(question, result, history, image_context)
    elif result.query_intent == "synthesis":
        messages = build_synthesis_prompt(question, result, history, image_context)
    else:
        messages = build_single_source_prompt(question, result, history, image_context)
        
    # 2. Call Groq
    try:
        client = _get_groq_client()
        response = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=messages,
            stream=False, # Instruction said collect tokens, but typically we return GeneratedAnswer non-streaming here
            timeout=GROQ_TIMEOUT
        )
        answer = response.choices[0].message.content
    except Exception as e:
        print(f"[MultiGenerator] Groq Error: {e}")
        answer = f"Error generating answer: {e}"

    # 3. Build citations
    citations = _build_citations(result.all_chunks)
    
    return GeneratedAnswer(
        answer=answer,
        citations=citations,
        chunks=result.all_chunks
    )
