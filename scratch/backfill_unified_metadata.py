import json
import sys
from pathlib import Path
from datetime import datetime

# Add project root to sys.path
sys.path.append(str(Path(__file__).resolve().parent.parent))

from backend.database.connection import get_connection

def backfill():
    print("Starting backfill for unified_metadata...")
    try:
        with get_connection() as conn:
            cursor = conn.cursor(dictionary=True)
            
            # Fetch legal chunks
            cursor.execute("""
                SELECT c.id, c.source_id, c.chunk_type, c.legal_metadata, s.type, s.title, s.language
                FROM chunks c
                JOIN sources s ON s.id = c.source_id
                WHERE c.unified_metadata IS NULL
            """)
            rows = cursor.fetchall()
            
            if not rows:
                print("No chunks need backfilling.")
                return

            print(f"Backfilling {len(rows)} chunks...")
            
            update_query = "UPDATE chunks SET unified_metadata = %s WHERE id = %s"
            batch = []
            
            for row in rows:
                legal_meta = {}
                if row['legal_metadata']:
                    if isinstance(row['legal_metadata'], str):
                        legal_meta = json.loads(row['legal_metadata'])
                    else:
                        legal_meta = row['legal_metadata']

                # Map source type
                stype = row['type']
                if stype == 'pdf':
                    # Check if it's a statute or judgment
                    cursor.execute("SELECT doc_type FROM legal_sources WHERE source_id = %s", (row['source_id'],))
                    ls = cursor.fetchone()
                    if ls:
                        stype = "legal_statute" if ls['doc_type'] == 'statute' else "legal_judgment"

                # Create unified metadata
                unified = {
                    "source_id"   : row['source_id'],
                    "source_type" : stype,
                    "source_title"  : row['title'],
                    "chunk_type"  : row['chunk_type'],
                    "language"    : row['language'] or 'en',
                    "domain"      : "law",
                    "topics"      : [],
                    "date_added"    : datetime.now().isoformat(),
                    "section_id"    : legal_meta.get("section_id"),
                    "section_title" : legal_meta.get("section_title"),
                }
                
                batch.append((json.dumps(unified), row['id']))
                
                if len(batch) >= 100:
                    cursor.executemany(update_query, batch)
                    conn.commit()
                    batch = []

            if batch:
                cursor.executemany(update_query, batch)
                conn.commit()
                
            print("Backfill complete.")

    except Exception as e:
        print(f"Backfill failed: {e}")

if __name__ == "__main__":
    backfill()
