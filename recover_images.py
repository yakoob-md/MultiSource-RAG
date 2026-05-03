
import os
import base64
from backend.database.connection import get_connection
from backend.vision.blip_captioner import caption_image_blip
from backend.ingestion.image_loader import mark_job_completed, mark_job_failed

def recover_pending_jobs():
    print("[Recovery] Searching for pending image jobs...")
    with get_connection() as conn:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT id, image_path FROM image_jobs WHERE status = 'pending'")
        jobs = cursor.fetchall()
        
    if not jobs:
        print("[Recovery] No pending jobs found.")
        return

    print(f"[Recovery] Found {len(jobs)} pending jobs. Starting processing...")
    
    for job in jobs:
        job_id = job['id']
        img_path = job['image_path']
        print(f"[Recovery] Processing {job_id} ({img_path})...")
        
        try:
            if not os.path.exists(img_path):
                print(f"[Recovery] Error: File not found at {img_path}")
                mark_job_failed(job_id, f"File not found: {img_path}")
                continue
                
            with open(img_path, "rb") as f:
                img_bytes = f.read()
                
            # This now uses the Groq Llama 4 Scout Vision model
            caption = caption_image_blip(img_bytes)
            
            if "error" in caption.lower() and "analysis error" in caption.lower():
                print(f"[Recovery] Failed to caption {job_id}: {caption}")
                mark_job_failed(job_id, caption)
            else:
                mark_job_completed(job_id, caption)
                print(f"[Recovery] ✓ Successfully processed {job_id}")
                
        except Exception as e:
            print(f"[Recovery] Exception on {job_id}: {e}")
            mark_job_failed(job_id, str(e))

if __name__ == "__main__":
    recover_pending_jobs()
