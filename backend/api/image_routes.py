from fastapi import APIRouter, UploadFile, File, HTTPException
import shutil
import tempfile
from pathlib import Path
from datetime import datetime, date

from backend.ingestion.image_loader import save_image_and_queue
from backend.database.connection import get_connection

router = APIRouter()

@router.post("/upload-image")
async def upload_image(file: UploadFile = File(...), context: str = ""):
    """
    Endpoint to upload an image and auto-caption it for the knowledge base.
    """
    try:
        # Read file bytes
        file_bytes = await file.read()
        
        # 1. Save and queue (Fixes FK violation by using NULL source_id internally)
        result = save_image_and_queue(file_bytes, file.filename, context)
        image_id = result["image_id"]
        
        # 2. IMMEDIATELY call captioner (Synchronous for now as per strategy)
        from backend.vision.blip_captioner import caption_image_blip
        from backend.ingestion.image_loader import mark_job_completed, mark_job_failed
        
        caption = caption_image_blip(file_bytes)
        
        if "error" in caption.lower() or "could not be captioned" in caption.lower():
            # Keep as pending for manual retry/LLaVA if it failed
            status = "pending"
            final_caption = None
        else:
            mark_job_completed(image_id, caption)
            status = "completed"
            final_caption = caption

        return {
            "image_id": image_id,
            "status": status,
            "caption": final_caption,
            "message": "Image uploaded and processed" if status == "completed" else "Image uploaded (caption pending)"
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Server error: {str(e)}")

@router.get("/image-jobs")
async def get_image_jobs():
    """
    Returns all image jobs ordered by creation date.
    """
    try:
        with get_connection() as conn:
            cursor = conn.cursor(dictionary=True)
            cursor.execute("""
                SELECT id, image_path, status, caption, error_message, created_at 
                FROM image_jobs 
                ORDER BY created_at DESC
            """)
            rows = cursor.fetchall()
            
            # Convert datetimes to isoformat
            for row in rows:
                if isinstance(row.get('created_at'), (datetime, date)):
                    row['created_at'] = row['created_at'].isoformat()
                    
            return {"jobs": rows}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/image-jobs/pending-count")
async def get_pending_count():
    """
    Returns the count of currently pending jobs.
    """
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM image_jobs WHERE status = 'pending'")
            count = cursor.fetchone()[0]
            return {"count": count}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
