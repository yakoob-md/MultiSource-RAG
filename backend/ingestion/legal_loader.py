import pdfplumber
import uuid
import shutil
import json
import re
import logging
from pathlib import Path
from backend.database.connection import get_connection
from backend.ingestion.chunker import chunk_text_with_pages
from backend.ingestion.embedder import embed_texts
from backend.vectorstore.faiss_store import add_vectors
from backend.config import UPLOAD_DIR

logger = logging.getLogger(__name__)

def extract_legal_metadata(text: str, doc_type: str) -> dict:
    """
    Extracts metadata from a legal document text using regex patterns.
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

    # Use first few pages for metadata extraction to improve accuracy for case names/courts
    top_text = text[:5000]

    # Court
    court_patterns = [
        r"(?i)IN THE SUPREME COURT OF INDIA",
        r"(?i)HIGH COURT OF [A-Z\s]+",
        r"(?i)DISTRICT COURT OF [A-Z\s]+",
        r"(?i)IN THE COURT OF [A-Z\s]+"
    ]
    for pattern in court_patterns:
        match = re.search(pattern, top_text)
        if match:
            metadata["court"] = match.group().strip()
            break

    # Date
    date_patterns = [
        r"\b\d{1,2}[-/]\d{1,2}[-/]\d{2,4}\b",
        r"\b[A-Z][a-z]+ \d{1,2}, \d{4}\b"
    ]
    for pattern in date_patterns:
        match = re.search(pattern, top_text)
        if match:
            metadata["date"] = match.group().strip()
            break

    # IPC Sections
    ipc_pattern = r"(?i)(?:Section|Sec\.|u/s|IPC)\s*(\d+[A-Z]*)"
    ipc_matches = re.findall(ipc_pattern, text)
    if ipc_matches:
        # Get unique sections and format them
        unique_sections = sorted(list(set(ipc_matches)))
        metadata["ipc_sections"] = [f"Section {s}" for s in unique_sections]

    # Case Name, Petitioner, Respondent
    # Look for patterns like "Petitioner vs Respondent"
    case_pattern = r"(?i)([A-Z\s,]+)\s+(?:vs|v\.|VERSUS)\s+([A-Z\s,]+)"
    case_match = re.search(case_pattern, top_text)
    if case_match:
        metadata["petitioner"] = case_match.group(1).strip()
        metadata["respondent"] = case_match.group(2).strip()
        metadata["case_name"] = f"{metadata['petitioner']} vs {metadata['respondent']}"

    # Citation
    citation_patterns = [
        r"\(\d{4}\)\s*\d+\s*SCC\s*\d+",
        r"AIR\s*\d{4}\s*SC\s*\d+"
    ]
    for pattern in citation_patterns:
        match = re.search(pattern, top_text)
        if match:
            metadata["citation"] = match.group().strip()
            break

    return metadata

def extract_chunk_metadata(chunk_text: str) -> dict:
    """
    Extracts chunk-level metadata (only IPC sections).
    """
    ipc_pattern = r"(?i)(?:Section|Sec\.|u/s|IPC)\s*(\d+[A-Z]*)"
    ipc_matches = re.findall(ipc_pattern, chunk_text)
    unique_sections = sorted(list(set(ipc_matches)))
    return {
        "ipc_sections": [f"Section {s}" for s in unique_sections]
    }

def ingest_legal_document(file_path: Path, filename: str, doc_type: str) -> dict:
    """
    Ingests a legal document into the RAG system.
    """
    if doc_type not in ['statute', 'judgment', 'constitution']:
        raise ValueError("doc_type must be one of: 'statute', 'judgment', 'constitution'")

    try:
        # a. Generate source_id
        source_id = str(uuid.uuid4())

        # b. Copy file to UPLOAD_DIR
        dest_path = UPLOAD_DIR / f"{source_id}_{filename}"
        shutil.copy(file_path, dest_path)

        # c. Extract text page by page
        pages = []
        full_text = ""
        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages:
                text = page.extract_text() or ""
                pages.append(text)
                full_text += text + "\n"

        # d. Extract legal metadata
        metadata = extract_legal_metadata(full_text, doc_type)

        # e. Call chunk_text_with_pages
        chunks_raw = chunk_text_with_pages(pages)
        
        # f. Process chunks and g. Embed
        chunks = []
        chunk_ids = []
        texts_to_embed = []
        
        for i, chunk_dict in enumerate(chunks_raw):
            chunk_text = chunk_dict['text']
            page_num = chunk_dict.get('page_number')
            
            chunk_metadata = extract_chunk_metadata(chunk_text)
            # Add global metadata to chunk metadata for context
            chunk_metadata.update({
                "case_name": metadata["case_name"],
                "court": metadata["court"],
                "date": metadata["date"],
                "citation": metadata["citation"]
            })
            
            chunk_id = str(uuid.uuid4())
            chunk_ids.append(chunk_id)
            texts_to_embed.append(chunk_text)
            
            chunks.append({
                "id": chunk_id,
                "text": chunk_text,
                "index": i,
                "page_number": page_num,
                "metadata": chunk_metadata
            })

        vectors = embed_texts(texts_to_embed)

        # h. Insert into sources table
        # i. Insert into legal_sources table
        # j. Insert each chunk into chunks table
        
        with get_connection() as conn:
            cursor = conn.cursor()
            
            # Insert into sources
            cursor.execute("""
                INSERT INTO sources (id, type, title, origin, language, chunk_count, status)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (source_id, 'pdf', filename, str(dest_path), 'en', len(chunks), 'completed'))
            
            # Insert into legal_sources
            judgment_date = None
            if metadata["date"]:
                # Attempt to parse date for SQL DATE format (YYYY-MM-DD)
                for fmt in ("%d/%m/%Y", "%m/%d/%Y", "%d-%m-%Y", "%B %d, %Y"):
                    try:
                        dt = re.sub(r'(\d+)(st|nd|rd|th)', r'\1', metadata["date"]) # Remove st, nd, rd, th
                        judgment_date = Path(dt).name # dummy parsing logic, better use datetime
                        # Actually let's just try to extract YYYY-MM-DD if possible or leave as NULL
                        break
                    except:
                        continue
            
            # Better date parsing
            from datetime import datetime
            sql_date = None
            if metadata["date"]:
                date_str = metadata["date"]
                # Clean up ordinal suffixes
                date_str = re.sub(r'(\d+)(st|nd|rd|th)', r'\1', date_str)
                for fmt in ("%d/%m/%Y", "%m/%d/%Y", "%d-%m-%Y", "%B %d, %Y", "%Y-%m-%d"):
                    try:
                        sql_date = datetime.strptime(date_str, fmt).strftime("%Y-%m-%d")
                        break
                    except ValueError:
                        continue

            cursor.execute("""
                INSERT INTO legal_sources (id, source_id, doc_type, court, judgment_date, ipc_sections, petitioner, respondent)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                str(uuid.uuid4()),
                source_id,
                doc_type,
                metadata["court"],
                sql_date,
                json.dumps(metadata["ipc_sections"]),
                metadata["petitioner"],
                metadata["respondent"]
            ))
            
            # Insert chunks
            for chunk in chunks:
                cursor.execute("""
                    INSERT INTO chunks (id, source_id, chunk_text, chunk_index, page_number, chunk_type, legal_metadata)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                """, (
                    chunk["id"],
                    source_id,
                    chunk["text"],
                    chunk["index"],
                    chunk["page_number"],
                    'legal',
                    json.dumps(chunk["metadata"])
                ))
            
            conn.commit()

        # k. Call add_vectors
        add_vectors(chunk_ids, vectors)

        # l. Return dict
        return {
            "source_id": source_id,
            "chunk_count": len(chunks),
            "title": filename,
            "doc_type": doc_type
        }

    except Exception as e:
        logger.error(f"Error in ingest_legal_document: {e}")
        raise