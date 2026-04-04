import uuid
import requests
from bs4 import BeautifulSoup

from backend.database.connection import get_connection
from backend.ingestion.chunker import chunk_text
from backend.ingestion.embedder import embed_texts
from backend.vectorstore.faiss_store import add_vectors


# ── Browser headers so websites don't block us ───────────────────────────────
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}

# ── HTML tags we want to remove completely ────────────────────────────────────
# These contain no useful content for RAG
TAGS_TO_REMOVE = [
    "script", "style", "nav", "footer", "header",
    "aside", "form", "button", "iframe", "advertisement"
]


def _scrape_url(url: str) -> tuple[str, str]:
    """
    Fetch a webpage and extract clean text content.

    Steps:
    1. HTTP GET the page with browser headers
    2. Parse HTML with BeautifulSoup
    3. Remove noise tags (nav, footer, scripts etc.)
    4. Extract page title
    5. Extract all remaining text

    Args:
        url: the full URL to scrape

    Returns:
        tuple of (title, clean_text)
    """
    print(f"[URL] Fetching: {url}")

    response = requests.get(url, headers=HEADERS, timeout=30)
    response.raise_for_status()   # raises error if 404, 403 etc.

    soup = BeautifulSoup(response.text, "lxml")

    # ── Remove noise tags ─────────────────────────────────────────────────────
    for tag in TAGS_TO_REMOVE:
        for element in soup.find_all(tag):
            element.decompose()

    # ── Extract title ─────────────────────────────────────────────────────────
    title_tag = soup.find("title")
    title     = title_tag.get_text(strip=True) if title_tag else url

    # ── Extract clean text ────────────────────────────────────────────────────
    # get_text() pulls all remaining text, separator="\n" keeps paragraph breaks
    raw_text = soup.get_text(separator="\n", strip=True)

    # Collapse multiple blank lines into single newlines
    lines      = [line.strip() for line in raw_text.splitlines() if line.strip()]
    clean_text = "\n".join(lines)

    print(f"[URL] Scraped title : {title}")
    print(f"[URL] Scraped length: {len(clean_text)} chars")

    return title, clean_text


def ingest_url(url: str) -> dict:
    """
    Full pipeline for a single URL:
    1. Scrape and clean the webpage
    2. Chunk the text
    3. Embed all chunks
    4. Save source metadata to MySQL
    5. Save chunks to MySQL
    6. Save vectors to FAISS

    Args:
        url: full URL string e.g. "https://en.wikipedia.org/wiki/Transformer_(deep_learning)"

    Returns:
        dict with source_id, chunk_count, title
    """
    print(f"[URL] Starting ingestion: {url}")

    # ── Step 1: Scrape the page ───────────────────────────────────────────────
    title, clean_text = _scrape_url(url)

    if not clean_text:
        raise ValueError(f"No content could be scraped from: {url}")

    # ── Step 2: Generate unique source ID ─────────────────────────────────────
    source_id = str(uuid.uuid4())

    # ── Step 3: Chunk the text ────────────────────────────────────────────────
    chunks = chunk_text(clean_text)
    print(f"[URL] Created {len(chunks)} chunks")

    if not chunks:
        raise ValueError("Text was scraped but chunking produced no results.")

    # ── Step 4: Embed all chunks ───────────────────────────────────────────────
    vectors = embed_texts(chunks)
    print(f"[URL] Embedded {len(vectors)} chunks")

    # ── Step 5: Save to MySQL ──────────────────────────────────────────────────
    with get_connection() as conn:
        cursor = conn.cursor()

        # Insert into sources table
        cursor.execute("""
            INSERT INTO sources (id, type, title, origin, language, chunk_count, status)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (
            source_id,
            "url",
            title,
            url,
            "en",
            len(chunks),
            "completed"
        ))

        # Insert each chunk into chunks table
        chunk_ids = []
        for i, chunk_text_str in enumerate(chunks):
            chunk_id = str(uuid.uuid4())
            chunk_ids.append(chunk_id)

            cursor.execute("""
                INSERT INTO chunks
                    (id, source_id, chunk_text, chunk_index, url_ref)
                VALUES (%s, %s, %s, %s, %s)
            """, (
                chunk_id,
                source_id,
                chunk_text_str,
                i,
                url        # every chunk links back to the source URL
            ))

        conn.commit()
        print(f"[URL] Saved to MySQL: {len(chunk_ids)} chunks")

    # ── Step 6: Save vectors to FAISS ─────────────────────────────────────────
    add_vectors(chunk_ids, vectors)
    print(f"[URL] Ingestion complete: {url}")

    return {
        "source_id":   source_id,
        "chunk_count": len(chunks),
        "title":       title
    }