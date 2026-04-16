import uuid
import shutil
import json
import logging
from datetime import datetime
from pathlib import Path

from backend.config import UPLOAD_DIR
from backend.database.connection import get_connection
from backend.ingestion.legal_loader import load_legal_document
from backend.ingestion.metadata_extractor import extract_metadata
from backend.ingestion.legal_chunker import chunk_legal_document
from backend.ingestion.embedder import embed_texts
from backend.vectorstore.faiss_store import add_vectors

logger = logging.getLogger(__name__)

def process_legal_document(file_path: Path, filename: str, doc_type: str) -> dict:
    """
    The orchestrator that links together file loading, metadata extraction,
    semantic chunking, and complex Dual-Pipeline databasing logic.
    """
    logger.info(f"[Orchestrator] Starting end-to-end ingestion for: {filename}")
    source_id = str(uuid.uuid4())

    try:
        # 1. Routing to Loader
        dest_path = UPLOAD_DIR / f"{source_id}_{filename}"
        shutil.copy2(file_path, dest_path)
        full_text, pages = load_legal_document(file_path)

        # 2. Routing to Extractor (LLM + Regex)
        metadata = extract_metadata(full_text, doc_type)

        # 3. Routing to Chunker (Section / Paragraph aware)
        chunks_data = chunk_legal_document(full_text, doc_type)
        if not chunks_data:
            raise ValueError("Pipeline Error: Legal chunker returned zero chunks.")

        # 4. Preparing Vectors and Embeddings
        texts_to_embed = []
        for chunk in chunks_data:
            texts_to_embed.append(chunk["text"])
        
        vectors = embed_texts(texts_to_embed)

        # 5. Pipeline Transaction: Write to Databases
        with get_connection() as conn:
            cursor = conn.cursor()

            # A. Basic Source Registration
            cursor.execute("""
                INSERT INTO sources (id, type, title, origin, language, chunk_count, status)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (source_id, "pdf", filename, str(dest_path), "en", len(chunks_data), "completed"))

            # B. Complex Legal Metadata Registration
            judgment_date = None
            if metadata["date"]:
                for fmt in ("%d/%m/%Y", "%m/%d/%Y", "%d-%m-%Y", "%B %d, %Y", "%Y-%m-%d"):
                    try:
                        judgment_date = datetime.strptime(metadata["date"], fmt).strftime("%Y-%m-%d")
                        break
                    except ValueError:
                        continue

            cursor.execute("""
                INSERT INTO legal_sources (id, source_id, doc_type, court, judgment_date, ipc_sections, petitioner, respondent)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                str(uuid.uuid4()),
                source_id,
                doc_type,
                metadata["court"],
                judgment_date,
                json.dumps(metadata.get("ipc_sections", [])),
                metadata["petitioner"],
                metadata["respondent"]
            ))

            # C. Chunk Registration (Enforcing chunk_type = 'legal' and JSON metadata)
            chunk_ids = []
            for i, chunk in enumerate(chunks_data):
                cid = str(uuid.uuid4())
                chunk_ids.append(cid)
                
                # Dynamic mapping of chunk-specific metadata retrieved from legal_chunker
                chunk_meta = {
                    "section_number": chunk.get("section_number"),
                    "section_title": chunk.get("section_title"),
                    "paragraph_number": chunk.get("paragraph_number"),
                    "global_ipc": metadata.get("ipc_sections", [])
                }

                # We map page_number default to None since legal blocks cross page boundaries.
                cursor.execute("""
                    INSERT INTO chunks (id, source_id, chunk_text, chunk_index, page_number, chunk_type, legal_metadata)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                """, (
                    cid,
                    source_id,
                    chunk["text"],
                    i,
                    None,
                    'legal',
                    json.dumps(chunk_meta)
                ))
            
            conn.commit()

        # 6. Synchronize into FAISS
        add_vectors(chunk_ids, vectors)
        
        # 7. Write Execution Log Snapshot
        processed_dir = Path("data/legal_processed")
        processed_dir.mkdir(parents=True, exist_ok=True)
        dump_path = processed_dir / f"{source_id}_processed.json"
        
        with open(dump_path, 'w', encoding='utf-8') as f:
            json.dump({
                "source_id": source_id,
                "filename": filename,
                "metadata_schema_match": metadata,
                "total_chunks": len(chunks_data),
                "chunks": chunks_data
            }, f, indent=4)

        logger.info(f"[Orchestrator] ✅ Legal Pipeline processed successfully. Log: {dump_path}")
        return {
            "source_id": source_id,
            "chunk_count": len(chunks_data),
            "title": filename,
            "doc_type": doc_type
        }

    except Exception as e:
        logger.error(f"[Orchestrator] 🚨 Critical pipeline failure: {e}")
        raise
