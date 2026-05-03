
from backend.database.connection import get_connection

with get_connection() as conn:
    cursor = conn.cursor()
    cursor.execute("UPDATE image_jobs SET status = 'pending' WHERE status = 'failed'")
    cursor.execute("UPDATE sources SET status = 'processing' WHERE id IN (SELECT source_id FROM image_jobs WHERE status = 'pending')")
    conn.commit()
    print("Reset failed jobs to pending.")
