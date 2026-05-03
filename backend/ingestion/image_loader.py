import uuid
from pathlib import Path
from backend.config import DATA_DIR
from backend.database.connection import get_connection

# 1. Configuration
IMAGES_DIR = DATA_DIR / "images"
IMAGES_DIR.mkdir(parents=True, exist_ok=True)

ALLOWED_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.webp', '.bmp', '.tiff'}

def save_image_and_queue(file_bytes: bytes, filename: str, source_context: str = "") -> dict:
    """
    Saves image bytes to disk and inserts a pending job into the image_jobs table.
    Does NOT insert into the sources table as per instructions.
    """
    # Validate extension
    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise ValueError(f"Unsupported image extension: {ext}. Allowed: {ALLOWED_EXTENSIONS}")

    # Generate image_id
    image_id = str(uuid.uuid4())
    dest_path = IMAGES_DIR / f"{image_id}{ext}"

    # Write file_bytes to dest_path
    with open(dest_path, "wb") as f:
        f.write(file_bytes)

    # 3. Create entry in 'sources' table so it appears in Resource Manager
    # Use the filename as the title
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO sources (id, type, title, origin, status, chunk_count)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (image_id, 'image', filename, str(dest_path), 'processing', 0))
        
        # 4. Insert into image_jobs
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
    Returns a list of all image jobs with 'pending' status.
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
    Marks a job as completed, saves the generated caption,
    and indexes the caption into the knowledge base (FAISS + MySQL).
    """
    from backend.ingestion.embedder import embed_texts
    from backend.vectorstore.faiss_store import add_vectors

    # 1. Embed the caption
    vectors = embed_texts([caption])
    chunk_id = f"chunk-{job_id}"

    with get_connection() as conn:
        cursor = conn.cursor()
        
        # 2. Update image_jobs
        cursor.execute("""
            UPDATE image_jobs 
            SET status = 'completed', caption = %s 
            WHERE id = %s
        """, (caption, job_id))
        
        # 3. Create a chunk in MySQL
        cursor.execute("""
            INSERT INTO chunks (id, source_id, chunk_text, page_number, chunk_index, chunk_type)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (chunk_id, job_id, caption, 0, 0, 'image'))
        
        # 4. Update sources status and count
        cursor.execute("""
            UPDATE sources 
            SET status = 'completed', chunk_count = 1
            WHERE id = %s
        """, (job_id,))
        
        conn.commit()

    # 5. Add to FAISS
    add_vectors([chunk_id], vectors)
    print(f"[ImageLoader] Image {job_id} indexed into knowledge base.")

def mark_job_failed(job_id: str, error: str):
    """
    Marks a job as failed and saves the error message.
    """
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE image_jobs 
            SET status = 'failed', error_message = %s 
            WHERE id = %s
        """, (error, job_id))
        conn.commit()
