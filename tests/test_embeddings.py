import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from backend.ingestion.embedder import embed_texts, embed_query
from backend.vectorstore.faiss_store import add_vectors, search_vectors, get_total_vectors

# Step 1 - Embed some test chunks
print("Testing embedder...")
chunks = [
    "Machine learning is a subset of artificial intelligence.",
    "Python is a popular programming language for data science.",
    "Neural networks are inspired by the human brain.",
]
vectors = embed_texts(chunks)
print(f"[SUCCESS] Embedded {len(vectors)} chunks, vector size: {len(vectors[0])}")

# Step 2 - Add to FAISS
print("\nTesting FAISS storage...")
fake_ids = ["chunk-001", "chunk-002", "chunk-003"]
add_vectors(fake_ids, vectors)
print(f"[SUCCESS] Total vectors in index: {get_total_vectors()}")

# Step 3 - Search
print("\nTesting search...")
query_vec = embed_query("What is artificial intelligence?")
results = search_vectors(query_vec, top_k=2)
print("[SUCCESS] Top 2 results:")
for r in results:
    idx = fake_ids.index(r["chunk_id"])
    print(f"   Score: {r['score']:.4f} | Text: {chunks[idx]}")