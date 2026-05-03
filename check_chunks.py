
from backend.database.connection import get_connection
import os

with get_connection() as conn:
    cursor = conn.cursor(dictionary=True)
    # Check sources
    cursor.execute("SELECT id, type, title FROM sources WHERE id LIKE 'dadd95de%'")
    sources = cursor.fetchall()
    print(f"Sources: {sources}")
    
    for s in sources:
        # Check chunks
        cursor.execute("SELECT id, chunk_type, chunk_text FROM chunks WHERE source_id = %s", (s['id'],))
        chunks = cursor.fetchall()
        print(f"Chunks for {s['id']}: {chunks}")
