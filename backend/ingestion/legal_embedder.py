import json
import uuid
import re
from pathlib import Path

from backend.database.connection import get_connection
from backend.ingestion.embedder import embed_texts
from backend.vectorstore.faiss_store import add_vectors

JSONL_PATH = Path("data/legal_processed/all_chunks.jsonl")
BATCH_SIZE = 32

def get_already_embedded_sources() -> set:
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT DISTINCT legal_metadata->>'$.source' FROM chunks WHERE chunk_type='legal'")
            rows = cursor.fetchall()
            
            sources = set()
            for row in rows:
                if row[0]:
                    val = row[0]
                    if isinstance(val, str):
                        val = val.strip('"')
                    sources.add(val)
            return sources
    except Exception as e:
        print(f"Warning checking embedded sources: {e}")
        return set()

def insert_source_record(source_name: str) -> str:
    source_uuid = str(uuid.uuid4())
    origin_path = f"data/legal_processed/{source_name}.json"
    
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT IGNORE INTO sources (id, type, title, origin, language, chunk_count, status)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (source_uuid, "pdf", source_name, origin_path, "en", 0, "completed"))
        conn.commit()
    return source_uuid

def has_hindi(text: str) -> bool:
    # Basic check for Devanagari script unicode block
    return bool(re.search(r'[\u0900-\u097F]', text))

def main():
    if not JSONL_PATH.exists():
        print(f"File {JSONL_PATH} not found. Run legal_chunker first.")
        return

    already_embedded = get_already_embedded_sources()
    print(f"Found {len(already_embedded)} sources already embedded. Skipping them.")

    source_map = {} 
    chunk_counts = {} 
    source_languages = {} 
    
    # Read to filter by idempotent sources and get true count
    all_valid_lines = []
    with open(JSONL_PATH, "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            chunk = json.loads(line)
            source_name = chunk.get("metadata", {}).get("source", "")
            if source_name not in already_embedded:
                all_valid_lines.append(chunk)

    total_chunks = len(all_valid_lines)
    if total_chunks == 0:
        print("No new chunks to embed. Exiting.")
        return

    print(f"Starting embedding for {total_chunks} new chunks...")

    batch = []
    processed = 0

    def process_batch(current_batch):
        nonlocal processed
        
        texts = [c["text"] for c in current_batch]
        vectors = embed_texts(texts)
        chunk_ids = [c["chunk_id"] for c in current_batch]
        
        add_vectors(chunk_ids, vectors)
        
        with get_connection() as conn:
            cursor = conn.cursor()
            for c in current_batch:
                meta = c.get("metadata", {})
                source_name = meta.get("source", "unknown")
                
                if source_name not in source_languages:
                    source_languages[source_name] = False
                if has_hindi(c.get("text", "")):
                    source_languages[source_name] = True
                
                if source_name not in source_map:
                    sid = insert_source_record(source_name)
                    source_map[source_name] = sid
                
                source_id = source_map[source_name]
                
                if source_name not in chunk_counts:
                    chunk_counts[source_name] = 0
                chunk_counts[source_name] += 1
                
                # Convert section_id to page_number gracefully
                doc_type = meta.get("doc_type", "statute")
                page_val = None
                if doc_type in ['statute', 'constitution']:
                    sid_raw = meta.get("section_id", "0")
                    m = re.match(r"\d+", str(sid_raw))
                    if m:
                        page_val = int(m.group())
                    else:
                        page_val = 0
                        
                legal_metadata_json = json.dumps(meta, ensure_ascii=False)
                c_idx = chunk_counts[source_name] - 1
                
                cursor.execute("""
                    INSERT INTO chunks (id, source_id, chunk_text, chunk_index, chunk_type, legal_metadata, page_number, timestamp_s, url_ref)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    c["chunk_id"], 
                    source_id, 
                    c.get("text", ""), 
                    c_idx, 
                    "legal", 
                    legal_metadata_json, 
                    page_val, 
                    None, 
                    None
                ))
            conn.commit()
            
        processed += len(current_batch)
        if processed % 100 < BATCH_SIZE:  # prints broadly every 100 chunks
            print(f"Embedded {processed}/{total_chunks} chunks...")

    for chunk in all_valid_lines:
        batch.append(chunk)
        if len(batch) >= BATCH_SIZE:
            process_batch(batch)
            batch = []
            
    if batch:
        process_batch(batch)

    # Final DB updates for exact state
    with get_connection() as conn:
        cursor = conn.cursor()
        for s_name, s_id in source_map.items():
            count = chunk_counts.get(s_name, 0)
            lang = "hi" if source_languages.get(s_name) else "en"
            cursor.execute("UPDATE sources SET chunk_count = %s, language = %s WHERE id = %s", (count, lang, s_id))
        conn.commit()

    print(f"Done. Total embedded: {processed} chunks across {len(source_map)} sources.")

if __name__ == "__main__":
    main()
