import uuid
import shutil
from pathlib import Path
import pdfplumber

from backend.config import UPLOAD_DIR
from backend.database.connection import get_connection
from backend.ingestion.chunker import chunk_text_with_pages
from backend.ingestion.embedder import embed_texts
from backend.vectorstore.faiss_store import add_vectors


def _extract_pages(file_path: Path) -> list[str]:
    """
    Extract text from each page using pdfplumber.
    For each page:
      - First extract tables and format them as readable text
      - Then extract remaining plain text
      - Combine both so nothing is lost
    """
    pages = []

    with pdfplumber.open(str(file_path)) as pdf:
        for page in pdf.pages:
            page_content = []

            # Extract tables first
            tables = page.extract_tables()
            for table in tables:
                for row in table:
                    clean_row = " | ".join(
                        cell.strip() for cell in row if cell and cell.strip()
                    )
                    if clean_row:
                        page_content.append(clean_row)

            # Extract plain text
            plain_text = page.extract_text() or ""
            if plain_text.strip():
                page_content.append(plain_text.strip())

            pages.append("\n".join(page_content))

    return pages


def ingest_pdf(file_path: Path, original_filename: str) -> dict:
    """
    Full pipeline for a single PDF file:
    1. Save file to uploads folder
    2. Extract text + tables from each page using pdfplumber
    3. Chunk the pages
    4. Embed all chunks
    5. Save source metadata to MySQL
    6. Save chunks to MySQL
    7. Save vectors to FAISS
    """
    print(f"[PDF] Starting ingestion: {original_filename}")

    source_id = str(uuid.uuid4())

    dest_path = UPLOAD_DIR / f"{source_id}_{original_filename}"
    shutil.copy2(file_path, dest_path)
    print(f"[PDF] Saved to: {dest_path}")

    pages = _extract_pages(file_path)
    print(f"[PDF] Extracted {len(pages)} pages")

    page_chunks = chunk_text_with_pages(pages)
    print(f"[PDF] Created {len(page_chunks)} chunks")

    if not page_chunks:
        raise ValueError("No text could be extracted from this PDF.")

    texts   = [c["text"] for c in page_chunks]
    vectors = embed_texts(texts)
    print(f"[PDF] Embedded {len(vectors)} chunks")

    with get_connection() as conn:
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO sources (id, type, title, origin, language, chunk_count, status)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (
            source_id, "pdf", original_filename,
            str(dest_path), "en", len(page_chunks), "completed"
        ))

        chunk_ids = []
        for i, chunk in enumerate(page_chunks):
            chunk_id = str(uuid.uuid4())
            chunk_ids.append(chunk_id)
            cursor.execute("""
                INSERT INTO chunks
                    (id, source_id, chunk_text, chunk_index, page_number)
                VALUES (%s, %s, %s, %s, %s)
            """, (
                chunk_id, source_id, chunk["text"], i, chunk["page_number"]
            ))

        conn.commit()
        print(f"[PDF] Saved to MySQL: {len(chunk_ids)} chunks")

    add_vectors(chunk_ids, vectors)
    print(f"[PDF] Ingestion complete: {original_filename}")

    return {
        "source_id":   source_id,
        "chunk_count": len(page_chunks),
        "title":       original_filename
    }