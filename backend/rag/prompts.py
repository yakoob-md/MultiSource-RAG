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

LEGAL_PROMPT_TEMPLATE = """You are a Senior Legal Analyst trained on Indian law. 
You have access to retrieved legal documents below.

RETRIEVED LEGAL CONTEXT:
{context}

QUESTION: {question}

REASONING (think step-by-step before answering):
1. Identify the specific legal provision(s) directly relevant to this question.
2. Note any amendments, exceptions, or qualifications to those provisions.
3. If this is a judgment question, identify the ratio decidendi vs obiter dicta.

FINAL ANSWER:

ANSWER:
[Your clear, plain-language answer citing the exact legal basis]

LEGAL BASIS:
[Direct quote from the retrieved context — use exact statutory language]

CITATIONS:
1. [Document] | [Section/Para] | [Court if applicable] | [Date if applicable]

AMENDMENTS & EXCEPTIONS:
[Any amendments to cited sections, or 'None mentioned in context']"""

def build_single_source_prompt(question: str, result: MultiSourceResult, history: list[dict] | None, image_context: str | None = None, is_legal: bool = False) -> list[dict]:
    context_parts = [_format_chunk_for_prompt(i, c) for i, c in enumerate(result.all_chunks, start=1)]
    context_block = "\n\n".join(context_parts)

    if is_legal:
        # Use the optimized legal template
        content = LEGAL_PROMPT_TEMPLATE.format(context=context_block, question=question)
        messages = [{"role": "system", "content": content}]
    else:
        system_prompt = """You are an expert research assistant. Answer accurately using ONLY the provided context.
        Cite every claim with [Source N] inline. Structure your answer with clear sections."""
        messages = [{"role": "system", "content": f"{system_prompt}\n\n{image_context or ''}\n\nRETRIEVED CONTEXT:\n{context_block}"}]

    if history:
        valid_history = [m for m in history if m.get('role') in ('user', 'assistant') and m.get('content')]
        # If legal, keep history very short to save context space for long law books
        history_limit = 3 if is_legal else 12
        messages.extend(valid_history[-history_limit:])
    
    if not is_legal:
        messages.append({"role": "user", "content": question})
    else:
        # For the legal template, the question is already in the system message.
        # But for LLM providers that require a user message, we might still need one.
        # However, to avoid duplication in Alpaca, we might want to handle it in llm_provider.py
        # For now, let's keep it consistent with the template's intent.
        messages.append({"role": "user", "content": "Please provide the legal analysis based on the context above."})
        
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

def build_deep_research_prompt(question: str, result: MultiSourceResult, history: list[dict] | None, is_legal: bool = False) -> list[dict]:
    """Highly structured prompt for the Deep Research 'Professional Memo' format."""
    context_parts = [_format_chunk_for_prompt(i, c) for i, c in enumerate(result.all_chunks, start=1)]
    context_block = "\n\n".join(context_parts)

    memo_structure = """
    Structure your answer as a formal RESEARCH MEMORANDUM with the following sections:
    
    # 📑 EXECUTIVE SUMMARY
    [A 2-3 sentence high-level summary of the findings]
    
    # 🔍 DETAILED ANALYSIS
    [A thorough, point-by-point breakdown. Cite every claim with [Source N] inline. 
     Compare and contrast findings from different sources. If sources contradict, highlight the divergence.]
    
    # ⚖️ LEGAL FRAMEWORK / CORE CONCEPTS
    [List relevant statutes, sections, or technical principles identified in the sources. 
     Explain the application of these concepts to the current query.]
    
    # 📜 PRECEDENTS / LANDMARK FINDINGS
    [List any specific case law or key research studies mentioned in the sources. 
     Explain WHY these are relevant to the query.]
    
    # 🎯 CONCLUSION
    [Synthesized final conclusion and next steps/implications. 
     Provide a professional recommendation based strictly on the retrieved data.]
    
    CRITICAL ANALYSIS GUIDELINES:
    1. REASONING: Show your work. Explain the logic used to connect source data to the conclusion.
    2. GROUNDING: Do not hallucinate. If the data isn't there, say "The provided context does not specify..."
    3. NEUTRALITY: Maintain a professional, objective tone throughout.
    """

    if is_legal:
        system_prompt = f"You are a Principal Legal Research Counsel. {memo_structure}"
    else:
        system_prompt = f"You are a Lead Research Scientist. {memo_structure}"

    messages = [
        {"role": "system", "content": f"{system_prompt}\n\nRETRIEVED RESEARCH DATA:\n{context_block}"}
    ]
    
    if history:
        messages.extend(history[-2:]) # Keep history very short
        
    messages.append({"role": "user", "content": f"Final Research Query: {question}"})
    return messages
