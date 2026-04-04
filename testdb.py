from backend.database.connection import get_connection

try:
    with get_connection() as conn:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SHOW TABLES")
        tables = cursor.fetchall()
        print("✅ Connected! Tables found:")
        for t in tables:
            print(" -", list(t.values())[0])
except Exception as e:
    print("❌ Connection failed:", e)