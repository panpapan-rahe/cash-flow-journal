"""User auth + helper queries."""
import sqlite3
import os
from werkzeug.security import generate_password_hash, check_password_hash

DATA_DIR = os.environ.get(
    "CASHFLOW_DATA_DIR",
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data"),
)


def format_user_code(user_id: int, username: str) -> str:
    return f"{user_id:04d}_{username}"


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
            user_code TEXT,
            password_hash TEXT NOT NULL,
            is_admin INTEGER NOT NULL DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)

    cols = {row[1] for row in conn.execute("PRAGMA table_info(users)").fetchall()}
    if "user_code" not in cols:
        conn.execute("ALTER TABLE users ADD COLUMN user_code TEXT")

    rows = conn.execute("SELECT id, username FROM users WHERE user_code IS NULL OR user_code = ''").fetchall()
    for row in rows:
        conn.execute("UPDATE users SET user_code = ? WHERE id = ?", (format_user_code(row['id'], row['username']), row['id']))

    conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_users_user_code ON users(user_code)")
    conn.commit()
    return conn


def create_user(username: str, password: str) -> int | None:
    conn = get_users_db()
    try:
        cursor = conn.execute(
            "INSERT INTO users (username, user_code, password_hash) VALUES (?, ?, ?)",
            (username, None, generate_password_hash(password))
        )
        user_id = cursor.lastrowid
        if user_id is None:
            raise sqlite3.DatabaseError('Failed to create user')
        conn.execute(
            "UPDATE users SET user_code = ? WHERE id = ?",
            (format_user_code(int(user_id), username), int(user_id))
        )
        conn.commit()
        return user_id
    except sqlite3.IntegrityError:
        return None
    finally:
        conn.close()


def authenticate(username: str, password: str) -> dict | None:
    conn = get_users_db()
    user = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
    conn.close()
    if user and check_password_hash(user["password_hash"], password):
        return {"id": user["id"], "username": user["username"], "user_code": user["user_code"], "is_admin": bool(user["is_admin"])}
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
