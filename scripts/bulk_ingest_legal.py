import os
import sys
from pathlib import Path
import logging

# Add project root to sys.path
sys.path.append(str(Path(__file__).resolve().parent.parent))

from backend.ingestion.legal_loader import ingest_legal_document
from scratch.backfill_unified_metadata import backfill

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

STATUTES_DIR = Path(r"c:\Users\dabaa\OneDrive\Desktop\dektop_content\Rag_System_2\data\legal_raw\statutes")
JUDGMENTS_DIR = Path(r"c:\Users\dabaa\OneDrive\Desktop\dektop_content\Rag_System_2\data\legal_raw\judgments\sc\2024")

def run_bulk_ingestion():
    # 1. Ingest Statutes
    if STATUTES_DIR.exists():
        logger.info(f"Scanning statutes in {STATUTES_DIR}...")
        for file in STATUTES_DIR.glob("*.pdf"):
            try:
                logger.info(f"Ingesting Statute: {file.name}")
                ingest_legal_document(file, file.name, "statute")
            except Exception as e:
                logger.error(f"Failed to ingest {file.name}: {e}")
    
    # 2. Ingest Judgments
    if JUDGMENTS_DIR.exists():
        logger.info(f"Scanning judgments in {JUDGMENTS_DIR}...")
        for file in JUDGMENTS_DIR.glob("*.pdf"):
            try:
                logger.info(f"Ingesting Judgment: {file.name}")
                ingest_legal_document(file, file.name, "judgment")
            except Exception as e:
                logger.error(f"Failed to ingest {file.name}: {e}")

    # 3. Run Backfill to populate unified_metadata
    logger.info("Running backfill for unified_metadata...")
    backfill()
    
    logger.info("Bulk ingestion and backfill complete.")

if __name__ == "__main__":
    run_bulk_ingestion()
