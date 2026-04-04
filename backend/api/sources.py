from fastapi import APIRouter, HTTPException
from backend.database.connection import get_connection
from backend.vectorstore.faiss_store import delete_vectors
from pathlib import Path
import os

router = APIRouter()


@router.get("/sources")
def get_sources():
    """
    GET /sources
    Returns all ingested sources for the frontend dashboard,
    knowledge sources page, and sidebar preview.
    """
    with get_connection() as conn:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT
                id,
                type,
                title,
                origin,
                language,
                chunk_count  AS chunkCount,
                status,
                created_at   AS createdAt
            FROM sources
            ORDER BY created_at DESC
        """)
        sources = cursor.fetchall()

    # Convert datetime to ISO string for JSON serialization
    for s in sources:
        if s["createdAt"]:
            s["createdAt"] = s["createdAt"].isoformat()

    return {"sources": sources}


@router.delete("/sources/{source_id}")
def delete_source(source_id: str):
    """
    DELETE /sources/{id}
    Deletes a source and all its chunks from FAISS, MySQL, and disk.
    """
    with get_connection() as conn:
        cursor = conn.cursor(dictionary=True)

        cursor.execute(
            "SELECT id, type, origin FROM sources WHERE id = %s",
            (source_id,)
        )
        source = cursor.fetchone()

        if not source:
            raise HTTPException(status_code=404, detail="Source not found")

        cursor.execute(
            "SELECT id FROM chunks WHERE source_id = %s",
            (source_id,)
        )
        chunk_rows = cursor.fetchall()
        chunk_ids  = {row["id"] for row in chunk_rows}

    if chunk_ids:
        delete_vectors(chunk_ids)

    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM sources WHERE id = %s", (source_id,))
        conn.commit()

    if source["type"] == "pdf" and source["origin"]:
        pdf_path = Path(source["origin"])
        if pdf_path.exists():
            os.remove(pdf_path)
            print(f"[Sources] Deleted file: {pdf_path}")

    print(f"[Sources] Deleted source: {source_id} ({len(chunk_ids)} chunks)")
    return {"message": "Source deleted successfully", "id": source_id}