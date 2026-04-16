import uuid
from pathlib import Path
from backend.config import DATA_DIR
from backend.database.connection import get_connection

# ── Configuration ─────────────────────────────────────────────────────────────

IMAGES_DIR = DATA_DIR / "images"
IMAGES_DIR.mkdir(parents=True, exist_ok=True)

ALLOWED_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.webp', '.bmp', '.tiff'}

def save_image_and_queue(file_bytes: bytes, filename: str, source_context: str = "") -> dict:
    """
    Saves the image to disk and creates a pending job in the image_jobs table.
    """
    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise ValueError(f"Unsupported image extension: {ext}. Allowed: {ALLOWED_EXTENSIONS}")

    image_id = str(uuid.uuid4())
    dest_path = IMAGES_DIR / f"{image_id}{ext}"

    # Write file bytes to destination
    with open(dest_path, "wb") as f:
        f.write(file_bytes)

    with get_connection() as conn:
        cursor = conn.cursor()
        
        # 1. Insert into base sources table
        cursor.execute("""
            INSERT INTO sources (id, type, title, origin, language, chunk_count, status)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (image_id, "image", filename, str(dest_path), "en", 1, "processing"))

        # 2. Insert into image_jobs table
        cursor.execute("""
            INSERT INTO image_jobs (id, source_id, image_path, status)
            VALUES (%s, %s, %s, %s)
        """, (image_id, image_id, str(dest_path), 'pending'))
        conn.commit()

    return {
        "image_id": image_id,
        "image_path": str(dest_path),
        "status": "pending",
        "filename": filename
    }

def get_pending_image_jobs() -> list[dict]:
    """
    Retrieves all image jobs that are currently in 'pending' status.
    """
    with get_connection() as conn:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT id, image_path 
            FROM image_jobs 
            WHERE status = 'pending' 
            ORDER BY created_at ASC
        """)
        return cursor.fetchall()

def mark_job_completed(job_id: str, caption: str):
    """
    Updates the status of an image job to 'completed' and sets the generated caption.
    """
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE image_jobs 
            SET status = 'completed', caption = %s 
            WHERE id = %s
        """, (caption, job_id))
        conn.commit()

def mark_job_failed(job_id: str, error: str):
    """
    Updates the status of an image job to 'failed' and records the error message.
    """
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE image_jobs 
            SET status = 'failed', error_message = %s 
            WHERE id = %s
        """, (error, job_id))
        conn.commit()
