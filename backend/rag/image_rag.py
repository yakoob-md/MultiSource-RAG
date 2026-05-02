# backend/rag/image_rag.py
# Phase 2: Image Understanding integrated into RAG pipeline
# When a user uploads an image alongside a question, this module:
# 1. Checks if there are completed caption jobs for the image
# 2. Injects the caption as extra context into the retriever
# 3. Lets the generator use BOTH document chunks + image description

import json
import base64
from pathlib import Path
from backend.database.connection import get_connection


def get_caption_for_image(image_id: str) -> str | None:
    """
    Retrieve a completed caption for a given image job id.
    Returns None if not found or not completed.
    """
    try:
        with get_connection() as conn:
            cursor = conn.cursor(dictionary=True)
            cursor.execute(
                "SELECT caption, status FROM image_jobs WHERE id = %s",
                (image_id,)
            )
            row = cursor.fetchone()
            if row and row["status"] == "completed" and row["caption"]:
                return row["caption"]
    except Exception as e:
        print(f"[ImageRAG] Error fetching caption: {e}")
    return None


def get_recent_completed_captions(limit: int = 3) -> list[dict]:
    """
    Get the most recently processed image captions.
    Used when user asks a question that might relate to uploaded images.
    """
    try:
        with get_connection() as conn:
            cursor = conn.cursor(dictionary=True)
            cursor.execute("""
                SELECT id, image_path, caption
                FROM image_jobs
                WHERE status = 'completed' AND caption IS NOT NULL
                ORDER BY updated_at DESC
                LIMIT %s
            """, (limit,))
            return cursor.fetchall()
    except Exception as e:
        print(f"[ImageRAG] Error fetching captions: {e}")
        return []


def build_image_context_block(captions: list[dict]) -> str:
    """
    Format image captions into a context block for the LLM prompt.
    Keeps it SHORT — 1-2 line description per image as per the strategy.
    """
    if not captions:
        return ""

    lines = ["[VISUAL CONTEXT FROM UPLOADED IMAGES]"]
    for cap in captions:
        img_name = Path(cap["image_path"]).name
        # Truncate to first 200 chars to keep GPU-efficient
        short_cap = cap["caption"][:200].strip()
        if len(cap["caption"]) > 200:
            short_cap += "..."
        lines.append(f"Image '{img_name}': {short_cap}")

    return "\n".join(lines)


def enrich_query_with_image_context(
    question: str,
    image_id: str | None = None,
    include_recent: bool = False
) -> tuple[str, str]:
    """
    Main entry point for Phase 2.

    Returns:
        (enriched_question, image_context_block)

    The enriched_question adds image description keywords so FAISS
    can retrieve relevant chunks.
    The image_context_block is injected into the system prompt.
    """
    image_context = ""
    enriched = question

    if image_id:
        caption = get_caption_for_image(image_id)
        if caption:
            short = caption[:150]
            enriched = f"{question}\n[Image shows: {short}]"
            image_context = f"[UPLOADED IMAGE DESCRIPTION]\n{caption[:300]}"

    elif include_recent:
        recent = get_recent_completed_captions(limit=2)
        if recent:
            image_context = build_image_context_block(recent)

    return enriched, image_context


def decode_base64_image(b64_data: str) -> bytes:
    """Decode a base64 image string to bytes (for direct upload flow)."""
    if "," in b64_data:
        b64_data = b64_data.split(",", 1)[1]
    return base64.b64decode(b64_data)
