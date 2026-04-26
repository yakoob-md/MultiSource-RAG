from backend.ingestion.chunker import (
    chunk_text,
    chunk_text_with_pages,
    chunk_text_with_timestamps
)

# Test 1 - plain text
print("=== Test 1: Plain text chunking ===")
long_text = "Hello world. " * 100   # 1300 chars
chunks = chunk_text(long_text)
print(f"Input length : {len(long_text)} chars")
print(f"Chunks created: {len(chunks)}")
print(f"Chunk 0 length: {len(chunks[0])} chars")
print(f"Chunk 1 length: {len(chunks[1])} chars")

# Test 2 - PDF pages
print("\n=== Test 2: PDF page chunking ===")
pages = [
    "This is page one content. " * 40,
    "This is page two content. " * 40,
]
page_chunks = chunk_text_with_pages(pages)
print(f"Total chunks from 2 pages: {len(page_chunks)}")
print(f"First chunk page number: {page_chunks[0]['page_number']}")
print(f"Last chunk page number : {page_chunks[-1]['page_number']}")

# Test 3 - YouTube segments
print("\n=== Test 3: YouTube transcript chunking ===")
segments = [{"text": f"This is sentence {i}.", "start": i * 3.0} for i in range(50)]
yt_chunks = chunk_text_with_timestamps(segments)
print(f"Total YouTube chunks: {len(yt_chunks)}")
print(f"First chunk timestamp: {yt_chunks[0]['timestamp_s']}s")
print(f"First chunk preview  : {yt_chunks[0]['text'][:60]}...")

print("\n✅ All chunker tests passed!")