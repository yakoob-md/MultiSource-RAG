from pathlib import Path
from backend.ingestion.pdf_loader import ingest_pdf

# Put any small PDF file in your project folder
# and change this path to point to it
pdf_path = Path("test.pdf")   # ← place any PDF here

if not pdf_path.exists():
    print("❌ Please place a PDF file named 'test.pdf' in the project root")
else:
    result = ingest_pdf(pdf_path, "test.pdf")
    print("\n✅ PDF ingestion result:")
    print(f"   source_id  : {result['source_id']}")
    print(f"   chunk_count: {result['chunk_count']}")
    print(f"   title      : {result['title']}")
    