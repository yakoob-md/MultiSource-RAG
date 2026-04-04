import shutil
import tempfile
from pathlib import Path
from fastapi import APIRouter, UploadFile, File, HTTPException
from pydantic import BaseModel
from backend.ingestion.pdf_loader     import ingest_pdf
from backend.ingestion.url_loader     import ingest_url
from backend.ingestion.youtube_loader import ingest_youtube

router = APIRouter()


# ── Request models ────────────────────────────────────────────────────────────

class UrlRequest(BaseModel):
    url: str
    language: str = "en"

class YoutubeRequest(BaseModel):
    url: str
    language: str = "en"


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/upload-pdf")
async def upload_pdf(file: UploadFile = File(...)):
    """
    POST /upload-pdf
    Accepts a PDF file upload, saves it temporarily,
    runs the full ingestion pipeline, returns source summary.
    """
    if not file.filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are accepted.")

    # Save uploaded file to a temp location first
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        shutil.copyfileobj(file.file, tmp)
        tmp_path = Path(tmp.name)

    try:
        result = ingest_pdf(tmp_path, file.filename)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        # Always clean up the temp file
        if tmp_path.exists():
            tmp_path.unlink()

    return {
        "message"    : "PDF ingested successfully",
        "source_id"  : result["source_id"],
        "title"      : result["title"],
        "chunk_count": result["chunk_count"]
    }


@router.post("/add-url")
def add_url(req: UrlRequest):
    """
    POST /add-url
    Accepts a website URL, scrapes and ingests it.
    Body: { "url": "https://...", "language": "en" }
    """
    if not req.url.startswith("http"):
        raise HTTPException(status_code=400, detail="Invalid URL. Must start with http:// or https://")

    try:
        result = ingest_url(req.url)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    return {
        "message"    : "URL ingested successfully",
        "source_id"  : result["source_id"],
        "title"      : result["title"],
        "chunk_count": result["chunk_count"]
    }


@router.post("/add-youtube")
def add_youtube(req: YoutubeRequest):
    """
    POST /add-youtube
    Accepts a YouTube URL, fetches transcript and ingests it.
    Body: { "url": "https://youtube.com/watch?v=...", "language": "en" }
    """
    if "youtube.com" not in req.url and "youtu.be" not in req.url:
        raise HTTPException(status_code=400, detail="Invalid YouTube URL.")

    try:
        result = ingest_youtube(req.url)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    return {
        "message"    : "YouTube video ingested successfully",
        "source_id"  : result["source_id"],
        "title"      : result["title"],
        "chunk_count": result["chunk_count"],
        "language"   : result["language"]
    }