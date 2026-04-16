import pdfplumber
import uuid
import shutil
import json
import re
import logging
from pathlib import Path
from datetime import datetime

from backend.config import UPLOAD_DIR
from backend.database.connection import get_connection
from backend.ingestion.chunker import chunk_text_with_pages
from backend.ingestion.embedder import embed_texts
from backend.vectorstore.faiss_store import add_vectors

logger = logging.getLogger(__name__)

def extract_legal_metadata(text: str, doc_type: str) -> dict:
    """
    Extracts high-level legal metadata from a document string.
    Keys: case_name, court, date, ipc_sections, petitioner, respondent, citation.
    """
    metadata = {
        "case_name": None,
        "court": None,
        "date": None,
        "ipc_sections": [],
        "petitioner": None,
        "respondent": None,
        "citation": None
    }
    
    # court
    court_match = re.search(r"(IN THE SUPREME COURT[\s\w]+|HIGH COURT OF [\s\w]+|DISTRICT COURT[\s\w]+)", text, re.IGNORECASE)
    if court_match:
        metadata["court"] = court_match.group(0).strip()
        
    # date
    date_match = re.search(r"(\d{1,2}[/\-]\d{1,2}[/\-]\d{4}|(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},\s+\d{4})", text, re.IGNORECASE)
    if date_match:
        metadata["date"] = date_match.group(0).strip()
        
    # ipc_sections
    ipc_matches = re.findall(r"(?:Section|IPC|u/s)\s+(\d+[A-Z]?)", text, re.IGNORECASE)
    if ipc_matches:
        metadata["ipc_sections"] = list(set([f"Section {m}" for m in ipc_matches]))
        
    # case_name, petitioner, respondent
    case_patterns = [r"(.+)\s+vs\.?\s+(.+)", r"(.+)\s+v\.\s+(.+)"]
    top_text = text[:4000]
    for pattern in case_patterns:
        case_match = re.search(pattern, top_text, re.IGNORECASE)
        if case_match:
            p_raw = case_match.group(1).strip().split('\n')[-1]
            r_raw = case_match.group(2).strip().split('\n')[0]
            metadata["petitioner"] = re.sub(r"^(Petitioner|Appellant|Plaintiff):\s*", "", p_raw, flags=re.IGNORECASE).strip()
            metadata["respondent"] = re.sub(r"^(Respondent|Defendant):\s*", "", r_raw, flags=re.IGNORECASE).strip()
            metadata["case_name"] = f"{metadata['petitioner']} vs {metadata['respondent']}"
            break
            
    # citation
    cit_match = re.search(r"(\(\d{4}\)\s+\d+\s+SCC\s+\d+|AIR\s+\d{4}\s+SC\s+\d+)", text, re.IGNORECASE)
    if cit_match:
        metadata["citation"] = cit_match.group(0).strip()
        
    return metadata

def extract_chunk_metadata(chunk_text: str) -> dict:
    """
    Extract chunk-level legal metadata.
    """
    ipc_matches = re.findall(r"(?:Section|IPC|u/s)\s+(\d+[A-Z]?)", chunk_text, re.IGNORECASE)
    sections = list(set([f"Section {m}" for m in ipc_matches]))
    return {"ipc_sections": sections}

def ingest_legal_document(file_path: Path, filename: str, doc_type: str) -> dict:
    try:
        source_id = str(uuid.uuid4())
        dest_path = UPLOAD_DIR / f"{source_id}_{filename}"
        
        shutil.copy2(file_path, dest_path)
        
        pages = []
        with pdfplumber.open(str(file_path)) as pdf:
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    pages.append(text)
                    
        full_text = "\n".join(pages)
        if not full_text:
            raise ValueError("No text could be extracted from PDF.")
            
        metadata = extract_legal_metadata(full_text, doc_type)
        
        chunks = chunk_text_with_pages(pages)
        
        for chunk in chunks:
            chunk_metadata = extract_chunk_metadata(chunk['text'])
            chunk['chunk_ipc'] = chunk_metadata['ipc_sections']
            
        texts_to_embed = [c['text'] for c in chunks]
        vectors = embed_texts(texts_to_embed)
        
        with get_connection() as conn:
            cursor = conn.cursor()
            
            # Insert into sources
            cursor.execute("""
                INSERT INTO sources (id, type, title, origin, language, chunk_count, status)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (source_id, "pdf", filename, str(dest_path), "en", len(chunks), "completed"))
            
            # Insert into legal_sources
            judgment_date = None
            if metadata["date"]:
                for fmt in ("%d/%m/%Y", "%m/%d/%Y", "%d-%m-%Y", "%B %d, %Y"):
                    try:
                        judgment_date = datetime.strptime(metadata["date"], fmt).strftime("%Y-%m-%d")
                        break
                    except ValueError:
                        continue
                        
            cursor.execute("""
                INSERT INTO legal_sources (id, source_id, doc_type, court, judgment_date, ipc_sections, petitioner, respondent)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                str(uuid.uuid4()), source_id, doc_type, metadata["court"], judgment_date,
                json.dumps(metadata.get("ipc_sections", [])), metadata["petitioner"], metadata["respondent"]
            ))
            
            # Insert each chunk
            chunk_ids = []
            for i, chunk in enumerate(chunks):
                cid = str(uuid.uuid4())
                chunk_ids.append(cid)
                
                chunk_legal_meta = {
                    "ipc_sections": chunk['chunk_ipc']
                }
                
                cursor.execute("""
                    INSERT INTO chunks (id, source_id, chunk_text, chunk_index, page_number, chunk_type, legal_metadata)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                """, (
                    cid, source_id, chunk['text'], i, chunk.get("page_number"), 'legal', json.dumps(chunk_legal_meta)
                ))
                
            conn.commit()
            
        add_vectors(chunk_ids, vectors)
        
        return {
            "source_id": source_id,
            "chunk_count": len(chunks),
            "title": filename,
            "doc_type": doc_type
        }

    except Exception as e:
        logger.error(f"Error executing ingest_legal_document: {e}")
        raise
