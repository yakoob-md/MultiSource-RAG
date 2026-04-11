from fastapi import APIRouter, UploadFile, File, HTTPException
from backend.ingestion.image_loader import save_image_and_queue
from backend.database.connection import get_connection
import datetime

router = APIRouter(prefix="/images", tags=["images"])

@router.post("/upload-image")
async def upload_image(file: UploadFile = File(...), context: str = ""):
    """
    Endpoint to upload an image and queue it for processing.
    """
    try:
        content = await file.read()
        result = save_image_and_queue(content, file.filename, context)
        return {
            "message": "Image queued for processing",
            "image_id": result["image_id"],
            "status": "pending"
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.get("/image-jobs")
async def get_image_jobs():
    """
    Retrieve all image jobs from the database.
    """
    with get_connection() as conn:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT id, image_path, status, caption, error_message, created_at 
            FROM image_jobs 
            ORDER BY created_at DESC
        """)
        jobs = cursor.fetchall()
        
        # Convert datetime objects to ISO format strings for JSON compatibility
        for job in jobs:
            if isinstance(job["created_at"], (datetime.datetime, datetime.date)):
                job["created_at"] = job["created_at"].isoformat()
                
        return {"jobs": jobs}

@router.get("/image-jobs/pending-count")
async def get_pending_count():
    """
    Get the count of currently pending image jobs.
    """
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM image_jobs WHERE status = 'pending'")
        count = cursor.fetchone()[0]
        return {"count": count}
