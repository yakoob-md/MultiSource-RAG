# backend/vision/embed_captions.py — NEW FILE
# Run this after captioner.py completes to make images searchable

import uuid
import json
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent.parent))

from backend.database.connection import get_connection
from backend.ingestion.embedder import embed_texts
from backend.vectorstore.faiss_store import add_vectors

def embed_completed_captions():
    """
    Finds completed image jobs whose captions haven't been embedded yet,
    embeds the captions, and stores them as chunks in the RAG system.
    """
    print("[CaptionEmbedder] Checking for completed captions to embed...")

    with get_connection() as conn:
        cursor = conn.cursor(dictionary=True)
        # Find completed jobs that don't yet have a chunk in the DB
        cursor.execute("""
            SELECT ij.id, ij.image_path, ij.caption
            FROM image_jobs ij
            WHERE ij.status = 'completed'
              AND ij.caption IS NOT NULL
              AND NOT EXISTS (
                  SELECT 1 FROM chunks c
                  WHERE c.chunk_type = 'image' 
                    AND c.image_path = ij.image_path
              )
        """)
        jobs = cursor.fetchall()

    if not jobs:
        print("[CaptionEmbedder] No new captions to embed.")
        return

    print(f"[CaptionEmbedder] Embedding {len(jobs)} new captions...")

    texts = [j["caption"] for j in jobs]
    vectors = embed_texts(texts)

    with get_connection() as conn:
        cursor = conn.cursor()

        # Ensure an "image" source exists (or create one per image)
        chunk_ids = []
        for i, job in enumerate(jobs):
            image_name = Path(job["image_path"]).name

            # Create a source record for this image
            source_id = str(uuid.uuid4())
            cursor.execute("""
                INSERT INTO sources (id, type, title, origin, language, chunk_count, status)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (source_id, 'pdf', f"Image: {image_name}", job["image_path"], 'en', 1, 'completed'))

            # Create the chunk
            chunk_id = str(uuid.uuid4())
            chunk_ids.append(chunk_id)

            cursor.execute("""
                INSERT INTO chunks 
                    (id, source_id, chunk_text, chunk_index, chunk_type, image_path, legal_metadata)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (
                chunk_id, source_id,
                job["caption"],
                0, 'image',
                job["image_path"],
                json.dumps({"caption_model": "llava-v1.6-mistral-7b", "image_id": job["id"]})
            ))

        conn.commit()

    add_vectors(chunk_ids, vectors)
    print(f"[CaptionEmbedder] Done. {len(jobs)} image captions now searchable via RAG.")

if __name__ == "__main__":
    embed_completed_captions()
