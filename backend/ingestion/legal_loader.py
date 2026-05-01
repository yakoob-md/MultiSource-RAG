# backend/ingestion/legal_loader.py — FIXED: use legal_chunker, not generic chunker

import pdfplumber
import uuid
import shutil
import json
import re
import logging
from pathlib import Path
from datetime import datetime

from backend.database.connection import get_connection
from backend.ingestion.legal_chunker import chunk_legal_document   # ← WAS chunk_text_with_pages
from backend.ingestion.embedder import embed_texts
from backend.vectorstore.faiss_store import add_vectors
from backend.config import UPLOAD_DIR
from backend.ingestion.metadata_extractor import extract_metadata

logger = logging.getLogger(__name__)

def ingest_legal_document(file_path: Path, filename: str, doc_type: str) -> dict:
    """
    Ingests a legal document using section/paragraph-aware chunking.
    Now uses metadata_extractor (LLM + regex fallback) and legal_chunker.
    """
    if doc_type not in ['statute', 'judgment', 'constitution']:
        raise ValueError("doc_type must be one of: 'statute', 'judgment', 'constitution'")

    try:
        source_id = str(uuid.uuid4())
        dest_path = UPLOAD_DIR / f"{source_id}_{filename}"
        shutil.copy(file_path, dest_path)

        # Extract full text
        full_text = ""
        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages:
                full_text += (page.extract_text() or "") + "\n"

        # Use LLM + regex metadata extractor (not the basic regex-only one)
        metadata = extract_metadata(full_text, doc_type)

        # ✅ KEY FIX: use section/paragraph-aware chunker
        chunks_data = chunk_legal_document(full_text, doc_type)

        if not chunks_data:
            raise ValueError("Legal chunker returned zero chunks.")

        texts_to_embed = [c["text"] for c in chunks_data]
        vectors = embed_texts(texts_to_embed)

        # Date parsing
        sql_date = None
        if metadata.get("date"):
            date_str = re.sub(r'(\d+)(st|nd|rd|th)', r'\1', metadata["date"])
            for fmt in ("%d/%m/%Y", "%m/%d/%Y", "%d-%m-%Y", "%B %d, %Y", "%Y-%m-%d"):
                try:
                    sql_date = datetime.strptime(date_str, fmt).strftime("%Y-%m-%d")
                    break
                except ValueError:
                    continue

        with get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute("""
                INSERT INTO sources (id, type, title, origin, language, chunk_count, status)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (source_id, 'pdf', filename, str(dest_path), 'en', len(chunks_data), 'completed'))

            cursor.execute("""
                INSERT INTO legal_sources 
                    (id, source_id, doc_type, court, judgment_date, ipc_sections, petitioner, respondent)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                str(uuid.uuid4()),
                source_id,
                doc_type,
                metadata.get("court"),
                sql_date,
                json.dumps(metadata.get("ipc_sections", [])),
                metadata.get("petitioner"),
                metadata.get("respondent")
            ))

            chunk_ids = []
            for i, chunk in enumerate(chunks_data):
                cid = str(uuid.uuid4())
                chunk_ids.append(cid)

                # Build rich legal metadata per chunk
                chunk_meta = {
                    "doc_type"        : doc_type,
                    "source"          : filename,
                    "case_name"       : metadata.get("case_name"),
                    "court"           : metadata.get("court"),
                    "date"            : metadata.get("date"),
                    "citation"        : metadata.get("citation"),
                    "section_number"  : chunk.get("section_number"),
                    "section_title"   : chunk.get("section_title"),
                    "paragraph_number": chunk.get("paragraph_number"),
                    "ipc_sections"    : metadata.get("ipc_sections", []),
                }

                cursor.execute("""
                    INSERT INTO chunks 
                        (id, source_id, chunk_text, chunk_index, page_number, chunk_type, legal_metadata)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                """, (
                    cid, source_id, chunk["text"], i,
                    None,  # legal chunks cross page boundaries
                    'legal',
                    json.dumps(chunk_meta)
                ))

            conn.commit()

        add_vectors(chunk_ids, vectors)

        return {
            "source_id"  : source_id,
            "chunk_count": len(chunks_data),
            "title"      : filename,
            "doc_type"   : doc_type
        }

    except Exception as e:
        logger.error(f"[LegalLoader] Failed: {e}")
        raise