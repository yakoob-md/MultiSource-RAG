import sys
import os
from unittest.mock import MagicMock, patch, mock_open

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.ingestion.image_loader import save_image_and_queue

@patch("backend.ingestion.image_loader.get_connection")
@patch("builtins.open", new_callable=mock_open)
@patch("pathlib.Path.mkdir")
def test_save_image_and_queue(mock_mkdir, mock_file, mock_get_conn):
    print("Testing save_image_and_queue...")
    
    # Mock database
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_get_conn.return_value.__enter__.return_value = mock_conn
    mock_conn.cursor.return_value = mock_cursor
    
    file_bytes = b"fake-image-data"
    filename = "test_image.png"
    
    result = save_image_and_queue(file_bytes, filename)
    
    print(f"Result: {result}")
    
    # Assertions
    assert "image_id" in result
    assert result["status"] == "pending"
    assert result["filename"] == "test_image.png"
    assert "images" in result["image_path"]
    
    # Verify file was "written"
    mock_file.assert_called()
    handle = mock_file()
    handle.write.assert_called_once_with(file_bytes)
    
    # Verify DB insert was called
    mock_cursor.execute.assert_called()
    args, _ = mock_cursor.execute.call_args
    assert "INSERT INTO image_jobs" in args[0]
    mock_conn.commit.assert_called_once()
    
    print("save_image_and_queue test passed!")

if __name__ == "__main__":
    try:
        test_save_image_and_queue()
    except Exception as e:
        print(f"\nTest failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
