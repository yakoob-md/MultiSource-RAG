import mysql.connector
from mysql.connector import pooling
from backend.config import DB_HOST, DB_PORT, DB_USER, DB_PASSWORD, DB_NAME

# ── Connection Pool ───────────────────────────────────────────────────────────
# A pool keeps several connections open and reuses them.
# This is much faster than opening a new connection on every API request.
_pool = pooling.MySQLConnectionPool(
    pool_name="rag_pool",
    pool_size=5,
    host=DB_HOST,
    port=DB_PORT,
    user=DB_USER,
    password=DB_PASSWORD,
    database=DB_NAME,
    charset="utf8mb4",
    collation="utf8mb4_unicode_ci",
    autocommit=False,
)


def get_connection():
    """
    Get a connection from the pool.
    Always use this inside a 'with' block so it auto-returns to pool.

    Usage:
        with get_connection() as conn:
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT * FROM sources")
            rows = cursor.fetchall()
            conn.commit()
    """
    return _pool.get_connection()