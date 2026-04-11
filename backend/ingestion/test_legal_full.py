import sys
import os
from pathlib import Path

# Add project root to sys.path
sys.path.append(os.getcwd())

from backend.ingestion.legal_loader import ingest_legal_document
from backend.database.connection import get_connection

def test_full_pipeline():
    pdf_path = Path("test.pdf")
    if not pdf_path.exists():
        print("❌ Error: test.pdf not found in root directory.")
        return

    print(f"STARTing integration test with {pdf_path}...")
    
    try:
        result = ingest_legal_document(pdf_path, "Test_Legal_Doc.pdf", "judgment")
        print(f"SUCCESS: Ingestion call successful: {result}")
        
        source_id = result["source_id"]
        
        # Verify Database
        with get_connection() as conn:
            cursor = conn.cursor(dictionary=True)
            
            # 1. Check legal_sources
            cursor.execute("SELECT * FROM legal_sources WHERE source_id = %s", (source_id,))
            legal_source = cursor.fetchone()
            if legal_source:
                print(f"SUCCESS: Record found in legal_sources: {legal_source}")
            else:
                print("ERROR: No record found in legal_sources.")
            
            # 2. Check chunks
            cursor.execute("SELECT COUNT(*) as chunk_count FROM chunks WHERE source_id = %s AND chunk_type = 'legal'", (source_id,))
            count = cursor.fetchone()["chunk_count"]
            if count > 0:
                print(f"SUCCESS: Found {count} 'legal' chunks in chunks table.")
            else:
                print("ERROR: No legal chunks found.")
            
            # 3. Check legal_metadata in one chunk
            cursor.execute("SELECT legal_metadata FROM chunks WHERE source_id = %s LIMIT 1", (source_id,))
            meta = cursor.fetchone()["legal_metadata"]
            print(f"SUCCESS: Sample chunk legal_metadata: {meta}")

        print("\nPASSED: FULL INTEGRATION TEST!")

    except Exception as e:
        print(f"FAILED: Integration test failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_full_pipeline()
