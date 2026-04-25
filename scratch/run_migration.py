import sys
import os
from pathlib import Path

# Add project root to sys.path
sys.path.append(str(Path(__file__).resolve().parent.parent))

from backend.database.connection import get_connection

def run_migration():
    sql_path = Path(__file__).resolve().parent.parent / "backend" / "database" / "migration_001_unified_metadata.sql"
    with open(sql_path, "r") as f:
        sql = f.read()

    commands = [cmd.strip() for cmd in sql.split(";") if cmd.strip()]

    with get_connection() as conn:
        cursor = conn.cursor()
        for command in commands:
            if command.upper().startswith("USE "):
                cursor.execute(command)
                continue
            
            print(f"Executing: {command}")
            try:
                cursor.execute(command)
                conn.commit()
                print("Success.")
            except Exception as e:
                if "Duplicate column name" in str(e) or "Duplicate key name" in str(e):
                    print(f"Skipping: Already exists.")
                else:
                    print(f"Failed: {e}")
        print("Migration process finished.")

if __name__ == "__main__":
    run_migration()
