# backend/api/conversations.py
import uuid
import json
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from backend.database.connection import get_connection

router = APIRouter()


class CreateConversationRequest(BaseModel):
    title: str = "New Chat"
    conv_type: str = "general"


class RenameRequest(BaseModel):
    title: str


@router.post("/conversations")
def create_conversation(req: CreateConversationRequest):
    """Create a new conversation (like clicking 'New Chat' in ChatGPT)."""
    conv_id = str(uuid.uuid4())
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO conversations (id, title, conv_type) VALUES (%s, %s, %s)",
            (conv_id, req.title, req.conv_type)
        )
        conn.commit()
    return {"id": conv_id, "title": req.title, "conv_type": req.conv_type}


@router.get("/conversations")
def list_conversations():
    """Return all conversations ordered by most recent."""
    with get_connection() as conn:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT c.id, c.title, c.conv_type, c.created_at, c.updated_at,
                   COUNT(h.id) AS message_count
            FROM conversations c
            LEFT JOIN chat_history h ON h.conversation_id = c.id
            GROUP BY c.id
            ORDER BY c.updated_at DESC
            LIMIT 50
        """)
        rows = cursor.fetchall()
    for r in rows:
        if r["created_at"]:
            r["created_at"] = r["created_at"].isoformat()
        if r["updated_at"]:
            r["updated_at"] = r["updated_at"].isoformat()
    return {"conversations": rows}


@router.get("/conversations/{conv_id}/messages")
def get_conversation_messages(conv_id: str):
    """Load full message history for a specific conversation."""
    with get_connection() as conn:
        cursor = conn.cursor(dictionary=True)
        # Verify conversation exists
        cursor.execute("SELECT id, title FROM conversations WHERE id = %s", (conv_id,))
        conv = cursor.fetchone()
        if not conv:
            raise HTTPException(status_code=404, detail="Conversation not found")

        cursor.execute("""
            SELECT id, question, answer, sources_used AS sourcesUsed, created_at AS createdAt
            FROM chat_history
            WHERE conversation_id = %s
            ORDER BY created_at ASC
        """, (conv_id,))
        messages = cursor.fetchall()

    for m in messages:
        if m["createdAt"]:
            m["createdAt"] = m["createdAt"].isoformat()
        if m["sourcesUsed"] and isinstance(m["sourcesUsed"], str):
            m["sourcesUsed"] = json.loads(m["sourcesUsed"])

    return {"conversation": conv, "messages": messages}


@router.patch("/conversations/{conv_id}")
def rename_conversation(conv_id: str, req: RenameRequest):
    """Rename a conversation."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE conversations SET title = %s WHERE id = %s",
            (req.title, conv_id)
        )
        conn.commit()
    return {"id": conv_id, "title": req.title}


@router.delete("/conversations/{conv_id}")
def delete_conversation(conv_id: str):
    """Delete a conversation and all its messages."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM conversations WHERE id = %s", (conv_id,))
        conn.commit()
    return {"message": "Conversation deleted", "id": conv_id}
