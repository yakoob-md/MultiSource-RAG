import json
from dataclasses import dataclass
from groq import Groq

from backend.rag.generator import _build_citations, GeneratedAnswer
from backend.rag.retriever import RetrievedChunk
from backend.database.connection import get_connection
from backend.config import GROQ_API_KEY, GROQ_MODEL, GROQ_TIMEOUT

def get_legal_metadata_for_chunks(chunk_ids: list[str]) -> dict[str, dict]:
    """
    Queries MySQL for legal metadata associated with a list of chunks.
    Only returns records where chunk_type is 'legal'.
    
    Returns:
        dict: mapping chunk_id -> parsed legal_metadata (dict)
    """
    if not chunk_ids:
        return {}

    placeholders = ", ".join(["%s"] * len(chunk_ids))
    legal_meta_map = {}

    with get_connection() as conn:
        cursor = conn.cursor(dictionary=True)
        cursor.execute(f"""
            SELECT id, legal_metadata 
            FROM chunks 
            WHERE id IN ({placeholders}) AND chunk_type = 'legal'
        """, chunk_ids)
        
        rows = cursor.fetchall()
        for row in rows:
            if row["legal_metadata"]:
                try:
                    meta = json.loads(row["legal_metadata"])
                    legal_meta_map[row["id"]] = meta
                except (json.JSONDecodeError, TypeError):
                    continue
                    
    return legal_meta_map

def build_legal_prompt_context(chunks: list[RetrievedChunk], legal_meta: dict) -> str:
    """
    Formats chunks into a context block, injecting legal metadata if available.
    """
    context_parts = []
    for chunk in chunks:
        meta = legal_meta.get(chunk.chunk_id)
        
        if meta and any(meta.values()):
            # Extracted fields from legal_metadata JSON
            court = meta.get("court", "Unknown Court")
            date = meta.get("judgment_date", "Unknown Date")
            sections = meta.get("ipc_sections", [])
            sections_str = ", ".join(sections) if sections else "Not specified"
            
            header = f"[SOURCE] {chunk.source_title} | Court: {court} | Date: {date} | Sections: {sections_str}"
            context_parts.append(f"{header}\n{chunk.chunk_text}")
        else:
            # Fallback for standard or missing metadata
            context_parts.append(f"[SOURCE] {chunk.source_title}\n{chunk.chunk_text}")
            
    return "\n\n---\n\n".join(context_parts)

def build_legal_system_prompt() -> str:
    """
    Returns the exact system prompt instructed for legal analysis.
    """
    return (
        "You are a legal information assistant specializing in Indian law. "
        "Answer questions using ONLY the legal documents provided below. "
        "Always cite the specific case name, court, and section number when relevant. "
        "Format your answer as: ANSWER: [your explanation] CITATIONS: [numbered list of sources used]. "
        "If the information is not in the provided context, say 'This information is not available in the loaded legal documents.' "
        "Never give legal advice — only explain what the law states."
    )

def generate_legal_answer(
    question: str, 
    chunks: list[RetrievedChunk], 
    history: list[dict] | None = None
) -> GeneratedAnswer:
    """
    Generates a legal-specific answer using chunks, metadata, and optional history.
    Uses non-streaming Groq call as per Prompt 5 requirements.
    """
    # 1. Fetch legal metadata for chunks
    chunk_ids = [c.chunk_id for c in chunks]
    legal_meta = get_legal_metadata_for_chunks(chunk_ids)
    
    # 2. Build context string
    context = build_legal_prompt_context(chunks, legal_meta)
    
    # 3. Build message list
    messages = [
        {"role": "system", "content": build_legal_system_prompt() + "\n\nLEGAL DOCUMENTS:\n" + context}
    ]
    
    # Include history turns (last 3 pairs = 6 messages)
    if history:
        messages.extend(history[-6:])
        
    messages.append({"role": "user", "content": question})
    
    # 4. Call Groq API
    if not GROQ_API_KEY:
        raise ValueError("GROQ_API_KEY is not configured.")
        
    client = Groq(api_key=GROQ_API_KEY)
    
    response = client.chat.completions.create(
        model=GROQ_MODEL,
        messages=messages,
        stream=False,
        timeout=GROQ_TIMEOUT
    )
    
    answer_text = response.choices[0].message.content
    
    # 5. Build citations and return GeneratedAnswer
    citations = _build_citations(chunks)
    
    return GeneratedAnswer(
        answer=answer_text,
        citations=citations,
        chunks=chunks
    )
