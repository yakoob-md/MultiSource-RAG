import uuid
import re
import requests
from youtube_transcript_api import YouTubeTranscriptApi

from backend.database.connection import get_connection
from backend.ingestion.chunker import chunk_text_with_timestamps
from backend.ingestion.embedder import embed_texts
from backend.vectorstore.faiss_store import add_vectors

LANGUAGE_PREFERENCE = ["en", "hi", "te"]


def _extract_video_id(url: str) -> str:
    patterns = [
        r"(?:v=)([a-zA-Z0-9_-]{11})",
        r"(?:youtu\.be/)([a-zA-Z0-9_-]{11})",
        r"(?:embed/)([a-zA-Z0-9_-]{11})",
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    raise ValueError(f"Could not extract video ID from URL: {url}")


def _segments_to_dicts(fetched) -> list[dict]:
    result = []
    for s in fetched:
        if isinstance(s, dict):
            result.append(s)
        else:
            result.append({
                "text":     s.text,
                "start":    s.start,
                "duration": getattr(s, "duration", 0),
            })
    return result


def _fetch_transcript(video_id: str) -> tuple[list[dict], str]:
    # v1.2.4 requires an instance, not a class call
    api = YouTubeTranscriptApi()

    for lang in LANGUAGE_PREFERENCE:
        try:
            fetched  = api.fetch(video_id, languages=[lang])
            segments = _segments_to_dicts(fetched)
            print(f"[YouTube] Found transcript in language: {lang}")
            return segments, lang
        except Exception:
            continue

    try:
        fetched  = api.fetch(video_id)
        segments = _segments_to_dicts(fetched)
        print(f"[YouTube] Found transcript (default language)")
        return segments, "en"
    except Exception as e:
        raise ValueError(f"Could not fetch transcript: {str(e)}")


def _get_video_title(video_id: str, url: str) -> str:
    try:
        oembed = (
            f"https://www.youtube.com/oembed"
            f"?url=https://www.youtube.com/watch?v={video_id}&format=json"
        )
        resp = requests.get(oembed, timeout=10)
        if resp.status_code == 200:
            return resp.json().get("title", url)
    except Exception:
        pass
    return url


def ingest_youtube(url: str) -> dict:
    print(f"[YouTube] Starting ingestion: {url}")

    video_id = _extract_video_id(url)
    print(f"[YouTube] Video ID: {video_id}")

    segments, language = _fetch_transcript(video_id)
    print(f"[YouTube] Fetched {len(segments)} transcript segments")

    title = _get_video_title(video_id, url)
    print(f"[YouTube] Title: {title}")

    source_id = str(uuid.uuid4())

    chunks = chunk_text_with_timestamps(segments)
    print(f"[YouTube] Created {len(chunks)} chunks")

    if not chunks:
        raise ValueError("Transcript was fetched but chunking produced no results.")

    texts   = [c["text"] for c in chunks]
    vectors = embed_texts(texts)
    print(f"[YouTube] Embedded {len(vectors)} chunks")

    with get_connection() as conn:
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO sources (id, type, title, origin, language, chunk_count, status)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (
            source_id, "youtube", title, url,
            language, len(chunks), "completed"
        ))

        chunk_ids = []
        for i, chunk in enumerate(chunks):
            chunk_id = str(uuid.uuid4())
            chunk_ids.append(chunk_id)
            ts = chunk["timestamp_s"]

            cursor.execute("""
                INSERT INTO chunks
                    (id, source_id, chunk_text, chunk_index, timestamp_s, url_ref)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (
                chunk_id, source_id, chunk["text"], i, ts,
                f"https://www.youtube.com/watch?v={video_id}&t={ts}s"
            ))

        conn.commit()
        print(f"[YouTube] Saved to MySQL: {len(chunk_ids)} chunks")

    add_vectors(chunk_ids, vectors)
    print(f"[YouTube] Ingestion complete: {title}")

    return {
        "source_id":   source_id,
        "chunk_count": len(chunks),
        "title":       title,
        "language":    language
    }