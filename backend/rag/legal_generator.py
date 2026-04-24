import json
from dataclasses import dataclass
from backend.rag.generator import _build_citations, GeneratedAnswer
from backend.rag.retriever import RetrievedChunk
from backend.database.connection import get_connection

def get_legal_metadata_for_chunks(chunk_ids: list[str]) -> dict[str, dict]:
    """
    Queries MySQL to retrieve legal_metadata for specific chunks.
    """
    if not chunk_ids:
        return {}

    legal_meta = {}
    try:
        with get_connection() as conn:
            cursor = conn.cursor(dictionary=True)
            # Create the IN clause with correct number of placeholders
            placeholders = ', '.join(['%s'] * len(chunk_ids))
            query = f"SELECT id, legal_metadata FROM chunks WHERE id IN ({placeholders}) AND chunk_type = 'legal'"
            cursor.execute(query, tuple(chunk_ids))
            rows = cursor.fetchall()

            for row in rows:
                meta_raw = row['legal_metadata']
                if meta_raw:
                    if isinstance(meta_raw, str):
                        legal_meta[row['id']] = json.loads(meta_raw)
                    else:
                        legal_meta[row['id']] = meta_raw
    except Exception as e:
        print(f"Error fetching legal metadata: {e}")
        # Return empty dict if query fails
    
    return legal_meta

def build_legal_prompt_context(chunks: list[RetrievedChunk], legal_meta: dict) -> str:
    """
    Formats retrieved chunks into a context string for the prompt, including legal metadata.
    """
    context_parts = []
    
    for chunk in chunks:
        cid = chunk.chunk_id
        meta = legal_meta.get(cid)
        
        if meta:
            court = meta.get("court") or "N/A"
            date = meta.get("date") or "N/A"
            ipc_sections = ", ".join(meta.get("ipc_sections", [])) or "N/A"
            
            header = f"[SOURCE] {chunk.source_title} | Court: {court} | Date: {date} | Sections: {ipc_sections}"
            context_parts.append(f"{header}\n{chunk.chunk_text}")
        else:
            context_parts.append(f"[SOURCE] {chunk.source_title}\n{chunk.chunk_text}")
            
    return "\n\n---\n\n".join(context_parts)

def build_legal_system_prompt() -> str:
    """
    Returns the specialized system prompt for the legal assistant.
    """
    return "You are a legal information assistant specializing in Indian law. Answer questions using ONLY the legal documents provided below. Always cite the specific case name, court, and section number when relevant. Format your answer as: ANSWER: [your explanation] CITATIONS: [numbered list of sources used]. If the information is not in the provided context, say 'This information is not available in the loaded legal documents.' Never give legal advice — only explain what the law states."

def generate_legal_answer(question: str, chunks: list[RetrievedChunk], history: list[dict] | None = None) -> GeneratedAnswer:
    """
    Orchestrates the generation of a legal answer using the Groq API.
    """
    # 1. Gather IDs and fetch metadata
    chunk_ids = [c.chunk_id for c in chunks]
    legal_meta = get_legal_metadata_for_chunks(chunk_ids)
    
    # 2. Build context and prompt
    context = build_legal_prompt_context(chunks, legal_meta)
    system_prompt = build_legal_system_prompt()
    
    # 3. Construct messages
    messages = [
        {"role": "system", "content": system_prompt + "\n\nLEGAL DOCUMENTS:\n" + context}
    ]
    
    # Include history turns (last 3 turns only as per prompt)
    if history:
        # Each turn is (user_msg, assistant_msg) in our system usually, 
        # or a flat list of dicts. The prompt says "last 3 turns".
        # If it's a list of dicts, we take last 6 messages (3 pairs).
        messages.extend(history[-6:])
        
    messages.append({"role": "user", "content": question})
    
    # 4. Call Groq API
    try:
        from groq import Groq
        from backend.config import GROQ_API_KEY, GROQ_MODEL
        
        groq_client = Groq(api_key=GROQ_API_KEY)
        
        response = groq_client.chat.completions.create(
            model=GROQ_MODEL,
            messages=messages,
            stream=False
        )
        
        answer = response.choices[0].message.content
        
        # 5. Build citations and return
        citations = _build_citations(chunks)
        return GeneratedAnswer(answer=answer, citations=citations, chunks=chunks)
        
    except Exception as e:
        print(f"Error in generate_legal_answer: {e}")
        # Fallback error answer
        return GeneratedAnswer(
            answer=f"Error generating legal answer: {str(e)}",
            citations=[],
            chunks=chunks
        )
