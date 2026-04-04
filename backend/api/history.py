from fastapi import APIRouter
from backend.database.connection import get_connection
import json

router = APIRouter()


@router.get("/history")
def get_history():
    """
    GET /history
    Returns all chat history from MySQL.
    Fixes the localStorage-only bug — history now persists permanently.

    Response:
    {
        "history": [
            {
                "id": "uuid",
                "question": "...",
                "answer": "...",
                "sourcesUsed": ["uuid1", "uuid2"],
                "createdAt": "2024-01-01T00:00:00"
            }
        ]
    }
    """
    with get_connection() as conn:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT
                id,
                question,
                answer,
                sources_used AS sourcesUsed,
                created_at   AS createdAt
            FROM chat_history
            ORDER BY created_at DESC
            LIMIT 100
        """)
        rows = cursor.fetchall()

    for row in rows:
        if row["createdAt"]:
            row["createdAt"] = row["createdAt"].isoformat()
        if row["sourcesUsed"] and isinstance(row["sourcesUsed"], str):
            row["sourcesUsed"] = json.loads(row["sourcesUsed"])

    return {"history": rows}


@router.delete("/history")
def clear_history():
    """
    DELETE /history
    Clears all chat history from MySQL.
    Wires up the 'Clear All Data' button in Settings.
    """
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM chat_history")
        conn.commit()

    return {"message": "Chat history cleared successfully"}