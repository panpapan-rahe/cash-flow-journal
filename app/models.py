"""User auth + helper queries."""
import sqlite3
import os
from werkzeug.security import generate_password_hash, check_password_hash

DATA_DIR = os.environ.get(
    "CASHFLOW_DATA_DIR",
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data"),
)

def get_users_db() -> sqlite3.Connection:
    os.makedirs(DATA_DIR, exist_ok=True)
    db_path = os.path.join(DATA_DIR, "users.db")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            is_admin INTEGER NOT NULL DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    conn.commit()
    return conn

def create_user(username: str, password: str) -> int | None:
    conn = get_users_db()
    try:
        cursor = conn.execute(
            "INSERT INTO users (username, password_hash) VALUES (?, ?)",
            (username, generate_password_hash(password))
        )
        conn.commit()
        return cursor.lastrowid
    except sqlite3.IntegrityError:
        return None
    finally:
        conn.close()

def authenticate(username: str, password: str) -> dict | None:
    conn = get_users_db()
    user = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
    conn.close()
    if user and check_password_hash(user["password_hash"], password):
        return {"id": user["id"], "username": user["username"], "is_admin": bool(user["is_admin"])}
    return None

def user_exists(username: str) -> bool:
    conn = get_users_db()
    row = conn.execute("SELECT 1 FROM users WHERE username = ?", (username,)).fetchone()
    conn.close()
    return row is not None

def get_user_count() -> int:
    conn = get_users_db()
    row = conn.execute("SELECT COUNT(*) as cnt FROM users").fetchone()
    conn.close()
    return row["cnt"]

def get_db_path(user_id: int) -> str:
    return os.path.join(DATA_DIR, f"user_{user_id}.db")

def delete_user(user_id: int) -> bool:
    conn = get_users_db()
    try:
        row = conn.execute("SELECT id FROM users WHERE id = ?", (user_id,)).fetchone()
        if not row:
            return False
        conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
        conn.commit()
    finally:
        conn.close()

    db_path = get_db_path(user_id)
    if os.path.exists(db_path):
        try:
            os.remove(db_path)
        except OSError:
            pass
    return True
