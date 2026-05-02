import mysql.connector
import sys
import os
from pathlib import Path

# Add the project root to sys.path so we can import backend
sys.path.append(str(Path(__file__).resolve().parent.parent))

from backend.database.connection import get_connection
from backend.config import DB_NAME

def run_setup():
    print("Starting Database Setup...")
    
    schema_path = Path(__file__).resolve().parent.parent / "backend" / "database" / "schema.sql"
    if not schema_path.exists():
        print(f"Error: Schema file not found: {schema_path}")
        return

    try:
        conn = get_connection()
        cursor = conn.cursor()

        # 1. Read and Execute schema.sql
        print(f"Reading {schema_path.name}...")
        with open(schema_path, 'r', encoding='utf-8') as f:
            schema_sql = f.read()

        # Split by semicolon to execute one by one
        # Use a more robust split for SQL files
        statements = schema_sql.split(';')
        for statement in statements:
            stmt = statement.strip()
            if stmt and not stmt.startswith('--'):
                try:
                    cursor.execute(stmt)
                except mysql.connector.Error as err:
                    if "already exists" in str(err).lower() or "Duplicate" in str(err):
                        continue
                    print(f"Warning on stmt: {stmt[:50]}... \n Error: {err}")

        # 2. Run additional migrations/checks
        print("Running additional safety checks...")
        
        # Ensure conversations table exists
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS conversations (
            id VARCHAR(36) PRIMARY KEY,
            title VARCHAR(500) DEFAULT 'New Chat',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
        );
        """)
        print("Table 'conversations' ready.")

        # Ensure conversation_id column in chat_history
        try:
            cursor.execute("ALTER TABLE chat_history ADD COLUMN conversation_id VARCHAR(36) DEFAULT NULL")
            print("Column 'conversation_id' added to 'chat_history'.")
        except mysql.connector.Error as err:
            if "Duplicate column name" in str(err):
                print("Column 'conversation_id' already exists in 'chat_history'.")
            else:
                print(f"Error adding column: {err}")

        # Modify image_jobs.source_id to be NULLable
        try:
            cursor.execute("ALTER TABLE image_jobs MODIFY COLUMN source_id VARCHAR(36) NULL")
            print("Column 'image_jobs.source_id' modified to NULLable.")
        except mysql.connector.Error as err:
            print(f"Error modifying column: {err}")

        conn.commit()
        cursor.close()
        conn.close()
        print("\nDatabase setup complete!")

    except Exception as e:
        print(f"Critical error during setup: {e}")

if __name__ == "__main__":
    run_setup()
