import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from backend.rag.retriever import retrieve
from backend.database.connection import get_connection

# Get a real source_id from MySQL first
with get_connection() as conn:
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT id, title, type FROM sources LIMIT 3")
    sources = cursor.fetchall()

print("=== Your sources ===")
for s in sources:
    print(f"  {s['type']} | {s['title']} | {s['id']}")

print("\n=== Test 1: Search ALL sources ===")
results = retrieve("What is a neural network?")
print(f"Retrieved {len(results)} chunks")
for i, c in enumerate(results):
    print(f"  Rank {i+1}: [{c.score:.4f}] {c.source_title} ({c.source_type})")

print("\n=== Test 2: Filter to YouTube only ===")
youtube_id = next((s["id"] for s in sources if s["type"] == "youtube"), None)
if youtube_id:
    filtered = retrieve("What is a neural network?", source_ids=[youtube_id])
    print(f"Retrieved {len(filtered)} chunks from YouTube only")
    for i, c in enumerate(filtered):
        print(f"  Rank {i+1}: [{c.score:.4f}] {c.source_title} at {c.timestamp_s}s")

print("\n=== Test 3: Filter to PDF only ===")
pdf_id = next((s["id"] for s in sources if s["type"] == "pdf"), None)
if pdf_id:
    filtered = retrieve("What is attention mechanism?", source_ids=[pdf_id])
    print(f"Retrieved {len(filtered)} chunks from PDF only")
    for i, c in enumerate(filtered):
        print(f"  Rank {i+1}: [{c.score:.4f}] page {c.page_number}")