from fastapi import APIRouter, UploadFile, File, Form, HTTPException
import shutil
import tempfile
from pathlib import Path
from datetime import date, datetime

from backend.ingestion.legal_loader import ingest_legal_document
from backend.database.connection import get_connection

router = APIRouter()

@router.post("/upload-legal")
async def upload_legal(file: UploadFile = File(...), doc_type: str = Form("judgment")):
    """Upload and process a legal document into the RAG pipeline."""
    
    # Validate extension
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported for legal documents.")
        
    # Validate document type
    allowed_types = ['statute', 'judgment', 'constitution']
    if doc_type not in allowed_types:
        raise HTTPException(status_code=400, detail=f"doc_type must be one of {allowed_types}")
        
    tmp_path = None
    try:
        # Create tempfile
        fd, tmp_file = tempfile.mkstemp(suffix=".pdf")
        tmp_path = Path(tmp_file)
        
        with open(tmp_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        # Ingestion pipeline
        result = ingest_legal_document(tmp_path, file.filename, doc_type)
        
        return {
            "message": "Legal document ingested",
            "source_id": result["source_id"],
            "title": result["title"],
            "chunk_count": result["chunk_count"],
            "doc_type": result["doc_type"]
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        # Cleanup
        if tmp_path and tmp_path.exists():
            try:
                tmp_path.unlink()
            except Exception:
                pass


@router.get("/legal-sources")
async def get_legal_sources():
    """Retrieve all processed legal sources with their metadata."""
    try:
        with get_connection() as conn:
            cursor = conn.cursor(dictionary=True)
            cursor.execute("""
                SELECT s.id, s.title, s.status, s.created_at, 
                       ls.doc_type, ls.court, ls.judgment_date 
                FROM sources s 
                JOIN legal_sources ls ON s.id = ls.source_id 
                ORDER BY s.created_at DESC
            """)
            rows = cursor.fetchall()
            
            # Format datetime properties for JSON compatibility
            for row in rows:
                if isinstance(row.get('created_at'), (datetime, date)):
                    row['created_at'] = row['created_at'].isoformat()
                if isinstance(row.get('judgment_date'), (datetime, date)):
                    row['judgment_date'] = row['judgment_date'].isoformat()
                    
            return {"sources": rows}
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
