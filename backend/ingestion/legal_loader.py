import uuid
import shutil
import json
import re
from datetime import datetime
from pathlib import Path
import pdfplumber

from backend.config import UPLOAD_DIR
from backend.database.connection import get_connection
from backend.ingestion.chunker import chunk_text_with_pages
from backend.ingestion.embedder import embed_texts
from backend.vectorstore.faiss_store import add_vectors

def extract_legal_metadata(text: str, doc_type: str) -> dict:
    """
    Extract high-level legal metadata from the full document text using regex.
    Returns keys: case_name, court, date, ipc_sections, petitioner, respondent, citation
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

    # 1. Court
    court_match = re.search(r"(IN THE SUPREME COURT OF INDIA|HIGH COURT OF [A-Z\s]+|DISTRICT COURT OF [A-Z\s]+)", text, re.IGNORECASE)
    if court_match:
        metadata["court"] = court_match.group(0).strip()

    # 2. Date (dd/mm/yyyy or Month dd, yyyy)
    date_match = re.search(r"(\d{1,2}[/\-]\d{1,2}[/\-]\d{4}|(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},\s+\d{4})", text, re.IGNORECASE)
    if date_match:
        metadata["date"] = date_match.group(0).strip()

    # 3. IPC Sections (Section 302, IPC 302, u/s 302)
    ipc_matches = re.findall(r"(?:Section|IPC|u/s)\s+(\d+[A-Z]?)", text, re.IGNORECASE)
    if ipc_matches:
        # Filter duplicates and format as "Section X"
        metadata["ipc_sections"] = list(set([f"Section {m}" for m in ipc_matches]))

    # 4. Case Name (search for vs or v. near top - check first 2000 chars)
    top_text = text[:2000]
    case_match = re.search(r"([A-Z\s\.]+)\s+(?:vs|v\.)\s+([A-Z\s\.]+)", top_text)
    if case_match:
        metadata["petitioner"] = case_match.group(1).strip()
        metadata["respondent"] = case_match.group(2).strip()
        metadata["case_name"] = f"{metadata['petitioner']} vs {metadata['respondent']}"

    # 5. Citation ((YEAR) 1 SCC 1 or AIR 2024 SC 1)
    citation_match = re.search(r"(\(\d{4}\)\s+\d+\s+SCC\s+\d+|AIR\s+\d{4}\s+SC\s+\d+)", text, re.IGNORECASE)
    if citation_match:
        metadata["citation"] = citation_match.group(0).strip()

    return metadata

def extract_chunk_metadata(chunk_text: str) -> dict:
    """
    Extract chunk-level legal metadata (specifically IPC sections).
    """
    ipc_matches = re.findall(r"(?:Section|IPC|u/s)\s+(\d+[A-Z]?)", chunk_text, re.IGNORECASE)
    sections = list(set([f"Section {m}" for m in ipc_matches]))
    return {"ipc_sections": sections}

def ingest_legal_document(file_path: Path, filename: str, doc_type: str) -> dict:
    """
    Full pipeline for legal document ingestion.
    Supports statutes, judgments, and constitutions.
    """
    print(f"[Legal] Starting ingestion for {doc_type}: {filename}")
    source_id = str(uuid.uuid4())

    try:
        # 1. Save file to uploads folder
        dest_path = UPLOAD_DIR / f"{source_id}_{filename}"
        shutil.copy2(file_path, dest_path)

        # 2. Extract text page by page
        pages = []
        with pdfplumber.open(str(file_path)) as pdf:
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    pages.append(text)
        
        full_text = "\n".join(pages)
        if not full_text:
            raise ValueError("No text extracted from PDF.")

        # 3. Extract global metadata
        metadata = extract_legal_metadata(full_text, doc_type)

        # 4. Chunk text
        chunks_data = chunk_text_with_pages(pages)
        if not chunks_data:
            raise ValueError("Could not create chunks from text.")

        # 5. Process each chunk for metadata & collect texts for embedding
        texts_to_embed = []
        for chunk in chunks_data:
            chunk["legal_metadata"] = extract_chunk_metadata(chunk["text"])
            texts_to_embed.append(chunk["text"])

        # 6. Embed all chunks
        vectors = embed_texts(texts_to_embed)

        # 7. Database Persistence
        with get_connection() as conn:
            cursor = conn.cursor()

            # a. Insert into sources
            cursor.execute("""
                INSERT INTO sources (id, type, title, origin, language, chunk_count, status)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (
                source_id, "pdf", filename, str(dest_path), "en", len(chunks_data), "completed"
            ))

            # b. Insert into legal_sources
            judgment_date = None
            if metadata["date"]:
                try:
                    # Try to parse different formats and convert to YYYY-MM-DD
                    for fmt in ("%d/%m/%Y", "%m/%d/%Y", "%d-%m-%Y", "%B %d, %Y"):
                        try:
                            judgment_date = datetime.strptime(metadata["date"], fmt).strftime("%Y-%m-%d")
                            break
                        except ValueError:
                            continue
                except Exception:
                    judgment_date = None

            cursor.execute("""
                INSERT INTO legal_sources (id, source_id, doc_type, court, judgment_date, ipc_sections, petitioner, respondent)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                str(uuid.uuid4()),
                source_id,
                doc_type,
                metadata["court"],
                judgment_date,
                json.dumps(metadata["ipc_sections"]),
                metadata["petitioner"],
                metadata["respondent"]
            ))

            # c. Insert chunks
            chunk_ids = []
            for i, chunk in enumerate(chunks_data):
                cid = str(uuid.uuid4())
                chunk_ids.append(cid)
                cursor.execute("""
                    INSERT INTO chunks (id, source_id, chunk_text, chunk_index, page_number, chunk_type, legal_metadata)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                """, (
                    cid,
                    source_id,
                    chunk["text"],
                    i,
                    chunk["page_number"],
                    'legal',
                    json.dumps(chunk["legal_metadata"])
                ))
            
            conn.commit()

        # 8. Sync with FAISS
        add_vectors(chunk_ids, vectors)

        print(f"[Legal] Ingestion complete: {filename} ({len(chunks_data)} chunks)")
        return {
            "source_id": source_id,
            "chunk_count": len(chunks_data),
            "title": filename,
            "doc_type": doc_type
        }

    except Exception as e:
        print(f"[Legal] Critical error during ingestion: {e}")
        # Ideally, we should clean up the half-uploaded file or DB records here
        raise

