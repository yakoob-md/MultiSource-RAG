import shutil
import tempfile
from pathlib import Path
from datetime import datetime, date
from fastapi import APIRouter, UploadFile, File, HTTPException
from backend.ingestion.legal_loader import ingest_legal_document
from backend.database.connection import get_connection

router = APIRouter(prefix="/legal", tags=["legal"])

def _serialize_row(row):
    """
    Convert datetime and date objects in a dictionary to ISO format strings.
    """
    new_row = {}
    for key, value in row.items():
        if isinstance(value, (datetime, date)):
            new_row[key] = value.isoformat()
        else:
            new_row[key] = value
    return new_row

@router.post("/upload-legal")
async def upload_legal(file: UploadFile = File(...), doc_type: str = "judgment"):
    """
    POST /legal/upload-legal
    Ingests a legal PDF document (Statute, Judgment, or Constitution).
    """
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are accepted for legal ingestion.")
    
    valid_types = ['statute', 'judgment', 'constitution']
    if doc_type not in valid_types:
        raise HTTPException(status_code=400, detail=f"Invalid doc_type. Must be one of {valid_types}")

    # Use a temp file to buffer the upload
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        shutil.copyfileobj(file.file, tmp)
        tmp_path = Path(tmp.name)

    try:
        result = ingest_legal_document(tmp_path, file.filename, doc_type)
        return {
            "message": "Legal document ingested successfully.",
            "source_id": result["source_id"],
            "title": result["title"],
            "chunk_count": result["chunk_count"],
            "doc_type": result["doc_type"]
        }
    except Exception as e:
        print(f"[API Legal] Ingestion failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        # Cleanup
        if tmp_path.exists():
            tmp_path.unlink()

@router.get("/legal-sources")
def list_legal_sources():
    """
    GET /legal/legal-sources
    Returns all ingested legal documents with their specific metadata.
    """
    try:
        with get_connection() as conn:
            # dictionary=True gives us rows as dicts
            cursor = conn.cursor(dictionary=True)
            query = """
                SELECT 
                    s.id, s.title, s.status, s.created_at, 
                    ls.doc_type, ls.court, ls.judgment_date, ls.petitioner, ls.respondent
                FROM sources s
                JOIN legal_sources ls ON s.id = ls.source_id
                ORDER BY s.created_at DESC
            """
            cursor.execute(query)
            rows = cursor.fetchall()
            
            # Serialize datetime objects for JSON
            serialized_rows = [_serialize_row(row) for row in rows]
            
            return {"sources": serialized_rows}
    except Exception as e:
        print(f"[API Legal] Query failed: {e}")
        raise HTTPException(status_code=500, detail="Could not retrieve legal sources.")
