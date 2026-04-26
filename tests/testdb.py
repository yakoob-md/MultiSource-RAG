import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from backend.database.connection import get_connection

try:
    with get_connection() as conn:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SHOW TABLES")
        tables = cursor.fetchall()
        print("[SUCCESS] Connected! Tables found:")
        for t in tables:
            print(" -", list(t.values())[0])
except Exception as e:
    print("[ERROR] Connection failed:", e)