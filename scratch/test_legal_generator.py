import sys
import os
from unittest.mock import MagicMock, patch

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.rag.retriever import RetrievedChunk
from backend.rag.legal_generator import (
    build_legal_prompt_context, 
    get_legal_metadata_for_chunks
)

def test_prompt_building():
    print("Testing build_legal_prompt_context...")
    
    chunks = [
        RetrievedChunk(
            chunk_id="c1",
            source_id="s1",
            source_type="pdf",
            source_title="Judgment_A.pdf",
            chunk_text="The accused was found guilty.",
            score=0.9,
            page_number=5,
            timestamp_s=None,
            url_ref=None,
            language="en"
        ),
        RetrievedChunk(
            chunk_id="c2",
            source_id="s2",
            source_type="pdf",
            source_title="Statute_B.pdf",
            chunk_text="Section 302 of IPC defines punishment for murder.",
            score=0.8,
            page_number=10,
            timestamp_s=None,
            url_ref=None,
            language="en"
        )
    ]
    
    legal_meta = {
        "c1": {
            "court": "Supreme Court of India",
            "judgment_date": "2023-01-15",
            "ipc_sections": ["IPC Section 302", "Section 120B"]
        }
    }
    
    context = build_legal_prompt_context(chunks, legal_meta)
    print("\nGenerated Context:\n")
    print(context)
    
    # Assertions
    assert "Supreme Court of India" in context
    assert "IPC Section 302, Section 120B" in context
    assert "Judgment_A.pdf" in context
    assert "Statute_B.pdf" in context
    print("\nPrompt building test passed!")

@patch("backend.rag.legal_generator.get_connection")
def test_metadata_fetching(mock_get_conn):
    print("\nTesting get_legal_metadata_for_chunks...")
    
    # Mock database
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_get_conn.return_value.__enter__.return_value = mock_conn
    mock_conn.cursor.return_value = mock_cursor
    
    mock_cursor.fetchall.return_value = [
        {"id": "c1", "legal_metadata": '{"court": "High Court", "ipc_sections": ["Section 420"]}'}
    ]
    
    meta_map = get_legal_metadata_for_chunks(["c1"])
    print(f"Meta Map: {meta_map}")
    
    assert "c1" in meta_map
    assert meta_map["c1"]["court"] == "High Court"
    assert "Section 420" in meta_map["c1"]["ipc_sections"]
    print("Metadata fetching test passed!")

if __name__ == "__main__":
    try:
        test_prompt_building()
        test_metadata_fetching()
    except Exception as e:
        print(f"\nTest failed: {e}")
        sys.exit(1)
