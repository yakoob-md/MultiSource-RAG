# backend/rag/prompts.py
from backend.rag.retriever import RetrievedChunk
from backend.rag.multi_retriever import MultiSourceResult
from backend.database.connection import get_connection
import json

def _fetch_unified_metadata(chunk_id: str) -> dict:
    try:
        with get_connection() as conn:
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT unified_metadata FROM chunks WHERE id = %s", (chunk_id,))
            row = cursor.fetchone()
            if row and row['unified_metadata']:
                meta = row['unified_metadata']
                if isinstance(meta, str):
                    return json.loads(meta)
                return meta
    except:
        pass
    return {}

def _format_chunk_for_prompt(rank: int, chunk: RetrievedChunk) -> str:
    meta_dict = _fetch_unified_metadata(chunk.chunk_id)
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
        if chunk.page_number:
            ref_detail = f"page {chunk.page_number}"
        elif chunk.timestamp_s is not None:
            ref_detail = f"at {chunk.timestamp_s}s"

    header = f"[{rank}] {chunk.source_title}"
    if ref_detail:
        header += f" — {ref_detail}"
    return f"{header}\n{chunk.chunk_text}"

def build_single_source_prompt(question: str, result: MultiSourceResult, history: list[dict] | None, image_context: str | None = None, is_legal: bool = False) -> list[dict]:
    if is_legal:
        system_prompt = """You are a legal information assistant for Indian law. Answer using ONLY the provided context.
        Structure: ANSWER, LEGAL BASIS (quote), CITATIONS (Document | Section/Para)."""
    else:
        system_prompt = """You are an expert research assistant. Answer accurately using ONLY the provided context.
        Cite every claim with [Source N] inline. Structure your answer with clear sections."""

    context_parts = [_format_chunk_for_prompt(i, c) for i, c in enumerate(result.all_chunks, start=1)]
    context_block = "\n\n".join(context_parts)
    
    messages = [{"role": "system", "content": f"{system_prompt}\n\n{image_context or ''}\n\nRETRIEVED CONTEXT:\n{context_block}"}]
    if history:
        valid_history = [m for m in history if m.get('role') in ('user', 'assistant') and m.get('content')]
        # If legal, keep history very short to save context space for long law books
        history_limit = 3 if is_legal else 12
        messages.extend(valid_history[-history_limit:])
    messages.append({"role": "user", "content": question})
    return messages

def build_comparison_prompt(question: str, result: MultiSourceResult, history: list[dict] | None, image_context: str | None = None, is_legal: bool = False) -> list[dict]:
    system_prompt = """You are a research analyst. Compare the provided sources objectively and thoroughly.
    Structure your answer EXACTLY as:
    ## Comparison Overview
    ## {first_source}
    ## {second_source}
    ## Key Differences
    ## Key Similarities
    ## Citations"""
    
    titles = list(result.source_groups.keys())
    s_prompt = system_prompt
    if len(titles) >= 2:
        s_prompt = s_prompt.replace("{first_source}", titles[0]).replace("{second_source}", titles[1])
    
    context_parts = []
    for title, chunks in result.source_groups.items():
        group_context = "\n".join([_format_chunk_for_prompt(i+1, c) for i, c in enumerate(chunks)])
        context_parts.append(f"=== SOURCE: {title} ===\n{group_context}")
    
    messages = [{"role": "system", "content": f"{s_prompt}\n\n{image_context or ''}\n\nRETRIEVED CONTEXT:\n{'\n\n'.join(context_parts)}"}]
    if history:
        valid_history = [m for m in history if m.get('role') in ('user', 'assistant') and m.get('content')]
        # If legal, keep history very short to save context space for long law books
        history_limit = 3 if is_legal else 12
        messages.extend(valid_history[-history_limit:])
    messages.append({"role": "user", "content": question})
    return messages

def build_synthesis_prompt(question: str, result: MultiSourceResult, history: list[dict] | None, image_context: str | None = None, is_legal: bool = False) -> list[dict]:
    system_prompt = """You are a research synthesizer. Consolidate and summarize information from MULTIPLE sources.
    Structure your answer EXACTLY as:
    ## Consolidated Answer
    ## By Source
    ## Common Themes
    ## Citations"""
    
    context_parts = []
    for title, chunks in result.source_groups.items():
        group_context = "\n".join([_format_chunk_for_prompt(i+1, c) for i, c in enumerate(chunks[:4])])
        context_parts.append(f"=== SOURCE: {title} ===\n{group_context}")
        
    messages = [{"role": "system", "content": f"{system_prompt}\n\n{image_context or ''}\n\nRETRIEVED CONTEXT:\n{'\n\n'.join(context_parts)}"}]
    if history:
        valid_history = [m for m in history if m.get('role') in ('user', 'assistant') and m.get('content')]
        # If legal, keep history very short to save context space for long law books
        history_limit = 3 if is_legal else 12
        messages.extend(valid_history[-history_limit:])
    messages.append({"role": "user", "content": question})
    return messages
