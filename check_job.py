
from backend.database.connection import get_connection

with get_connection() as conn:
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT id, status FROM sources WHERE id LIKE 'dadd95de%'")
    print(f"Source Status: {cursor.fetchall()}")
    
    cursor.execute("SELECT * FROM image_jobs WHERE source_id LIKE 'dadd95de%'")
    print(f"Image Job: {cursor.fetchall()}")
