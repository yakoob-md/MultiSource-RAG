from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List
import json
from groq import Groq

from backend.rag.retriever import retrieve
from backend.database.connection import get_connection
from backend.config import GROQ_API_KEY, GROQ_MODEL

router = APIRouter()

class LegalQueryRequest(BaseModel):
    question: str
    source_filter: Optional[str] = None
    language: str = "en"

@router.post("/legal-query")
async def legal_query(req: LegalQueryRequest):
    # 1. Retrieve chunks
    try:
        retrieved = retrieve(req.question, source_ids=None)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Retrieval failed: {str(e)}")

    if not retrieved:
        return {
            "answer": "Not found in loaded documents.",
            "legal_basis": "",
            "citations": [],
            "retrieved_chunks": []
        }

    chunk_ids = [c.chunk_id for c in retrieved]

    # 2 & 3. Fetch from DB and Filter
    legal_chunks = []
    
    if chunk_ids:
        with get_connection() as conn:
            cursor = conn.cursor(dictionary=True)
            format_strings = ','.join(['%s'] * len(chunk_ids))
            query = f"SELECT id, chunk_type, legal_metadata FROM chunks WHERE id IN ({format_strings})"
            cursor.execute(query, tuple(chunk_ids))
            db_rows = cursor.fetchall()

        db_map = {row['id']: {"chunk_type": row['chunk_type'], "legal_metadata": row['legal_metadata']} for row in db_rows}

        for idx, c in enumerate(retrieved):
            db_info = db_map.get(c.chunk_id, {})
            chunk_type = db_info.get("chunk_type")

            if chunk_type != 'legal':
                continue
                
            metadata_raw = db_info.get("legal_metadata")
            if metadata_raw:
                if isinstance(metadata_raw, str):
                    try:
                        meta = json.loads(metadata_raw)
                    except:
                        meta = {}
                else:
                    meta = metadata_raw
            else:
                meta = {}

            doc_type = meta.get("doc_type", "")
            
            # Apply source filter if present
            if req.source_filter and doc_type != req.source_filter:
                continue
                
            legal_chunks.append({
                "chunk_id": c.chunk_id,
                "text": c.chunk_text,
                "source_title": c.source_title,
                "metadata": meta,
                "score": c.score
            })

    if not legal_chunks:
        return {
            "answer": "Not found in loaded documents matching legal filters.",
            "legal_basis": "",
            "citations": [],
            "retrieved_chunks": []
        }

    # Build Context Blocks
    context_blocks = []
    citations_structured = []
    
    for i, c in enumerate(legal_chunks):
        meta = c.get("metadata", {})
        doc_type = meta.get("doc_type", "")
        
        title = meta.get("title", "")
        case_name = meta.get("case_name", "")
        section_id = meta.get("section_id", "")
        court = meta.get("court", "")
        date_str = meta.get("date", "")
        amend_list = meta.get("amendments", [])
        amends_str = ", ".join(amend_list) if amend_list else "None"
        
        ident = f"Section {section_id}" if section_id else f"{case_name}"
        
        block = f"--- SOURCE {i + 1}: {c.get('source_title')} | {ident} ---\n"
        block += f"{c.get('text')}\n"
        block += f"Metadata: Court={court}, Date={date_str}, Amendments={amends_str}\n---\n"
        context_blocks.append(block)
        
        # Build structured citations based on deterministic data
        if doc_type == "statute":
            citations_structured.append({
                "document": c.get("source_title", ""),
                "section": section_id,
                "title": title,
                "text_excerpt": c.get("text", "")[:150] + "...",
                "amendments": amend_list,
                "source_type": "statute"
            })
        elif doc_type == "judgment":
            citations_structured.append({
                "document": meta.get("case_name", c.get("source_title", "")),
                "court": court,
                "date": date_str,
                "para": meta.get("para_range", ""),
                "text_excerpt": c.get("text", "")[:150] + "...",
                "source_type": "judgment"
            })

    # 4. Build Prompt
    system_prompt = """You are a legal information assistant for Indian law. Answer ONLY from the provided legal documents.
Format your answer in this EXACT structure:

ANSWER:
[Clear explanation in plain language]

LEGAL BASIS:
[Exact statutory text or judgment quote]

CITATIONS:
1. [Document] | [Section/Para] | [Court if applicable] | [Date if applicable]
2. ...

AMENDMENTS & NOTES:
[List any relevant amendments to the cited sections]

IMPORTANT: Never give legal advice. State what the law says, not what to do.
If information is not in the context, say "Not found in loaded documents."
"""
    
    user_prompt = "CONTEXT:\n" + "\n".join(context_blocks) + f"\n\nUSER: {req.question}"

    # 5. Call Groq
    try:
        client = Groq(api_key=GROQ_API_KEY)
        response = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.0
        )
        llm_output = response.choices[0].message.content
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"LLM Generation failed: {str(e)}")

    # 6. Parse response gracefully
    answer = ""
    legal_basis = ""
    
    lines = llm_output.split('\n')
    current_section = None
    
    answer_lines = []
    basis_lines = []
    
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("ANSWER:"):
            current_section = "ANSWER"
            if len(stripped) > 7: answer_lines.append(stripped[7:].strip())
            continue
        elif stripped.startswith("LEGAL BASIS:"):
            current_section = "LEGAL_BASIS"
            if len(stripped) > 12: basis_lines.append(stripped[12:].strip())
            continue
        elif stripped.startswith("CITATIONS:"):
            current_section = "CITATIONS"
            continue
        elif stripped.startswith("AMENDMENTS & NOTES:"):
            current_section = "AMENDMENTS"
            continue
            
        if current_section == "ANSWER":
            answer_lines.append(line)
        elif current_section == "LEGAL_BASIS":
            basis_lines.append(line)

    final_answer = "\n".join(answer_lines).strip()
    final_basis = "\n".join(basis_lines).strip()

    # 7. Return
    return {
        "answer": final_answer or llm_output,
        "legal_basis": final_basis,
        "citations": citations_structured,
        "retrieved_chunks": legal_chunks
    }
