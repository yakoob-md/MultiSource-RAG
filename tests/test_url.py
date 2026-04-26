import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from backend.ingestion.url_loader import ingest_url

# Test with a real webpage
result = ingest_url("https://en.wikipedia.org/wiki/Transformer_(deep_learning_architecture)")

print("\n[SUCCESS] URL ingestion result:")
print(f"   source_id  : {result['source_id']}")
print(f"   chunk_count: {result['chunk_count']}")
print(f"   title      : {result['title']}")