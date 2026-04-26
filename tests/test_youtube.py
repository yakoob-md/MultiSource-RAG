import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from backend.ingestion.youtube_loader import ingest_youtube

# 3Blue1Brown - But what is a neural network?
# Great test video - has English captions, ~18 mins
result = ingest_youtube("https://www.youtube.com/watch?v=aircAruvnKk")

print("\n[SUCCESS] YouTube ingestion result:")
print(f"   source_id  : {result['source_id']}")
print(f"   chunk_count: {result['chunk_count']}")
print(f"   title      : {result['title']}")
print(f"   language   : {result['language']}")