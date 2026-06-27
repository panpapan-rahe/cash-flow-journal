"""Database loader - creates/loads per-user SQLite databases."""
import sqlite3
import os
from flask import g

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")

def get_db_path(user_id: int) -> str:
    return os.path.join(DATA_DIR, f"user_{user_id}.db")

def get_db(user_id: int) -> sqlite3.Connection:
    if "db" not in g:
        os.makedirs(DATA_DIR, exist_ok=True)
        db_path = get_db_path(user_id)
        conn = sqlite3.connect(db_path, timeout=30)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA busy_timeout=30000")
        init_tables(conn)
        g.db = conn
    return g.db

def init_tables(conn: sqlite3.Connection):
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            type TEXT NOT NULL CHECK(type IN ('income', 'expense', 'transfer')),
            user_id INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS accounts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            opening_balance REAL NOT NULL DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category_id INTEGER REFERENCES categories(id),
            account_id INTEGER REFERENCES accounts(id),
            to_account_id INTEGER REFERENCES accounts(id),
            type TEXT NOT NULL CHECK(type IN ('income', 'expense', 'transfer')),
            amount REAL NOT NULL CHECK(amount > 0),
            admin_fee REAL DEFAULT 0,
            description TEXT,
            date DATE NOT NULL DEFAULT (date('now')),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS debts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            person_name TEXT NOT NULL,
            account_id INTEGER REFERENCES accounts(id),
            payment_account_id INTEGER REFERENCES accounts(id),
            debt_kind TEXT NOT NULL DEFAULT 'regular' CHECK(debt_kind IN ('regular', 'opening')),
            amount_total REAL NOT NULL CHECK(amount_total > 0),
            amount_paid REAL NOT NULL DEFAULT 0 CHECK(amount_paid >= 0),
            description TEXT,
            status TEXT NOT NULL DEFAULT 'active' CHECK(status IN ('active', 'paid')),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS debt_payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            debt_id INTEGER NOT NULL REFERENCES debts(id) ON DELETE CASCADE,
            transaction_id INTEGER REFERENCES transactions(id) ON DELETE SET NULL,
            amount REAL NOT NULL CHECK(amount > 0),
            note TEXT,
            date DATE NOT NULL DEFAULT (date('now')),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)

    # Migration: older DBs may not have transaction_id yet
    cols = {row[1] for row in conn.execute("PRAGMA table_info(debt_payments)").fetchall()}
    if "transaction_id" not in cols:
        conn.execute("ALTER TABLE debt_payments ADD COLUMN transaction_id INTEGER REFERENCES transactions(id) ON DELETE SET NULL")

    debt_cols = {row[1] for row in conn.execute("PRAGMA table_info(debts)").fetchall()}
    if "debt_kind" not in debt_cols:
        conn.execute("ALTER TABLE debts ADD COLUMN debt_kind TEXT NOT NULL DEFAULT 'regular'")
        conn.execute("UPDATE debts SET debt_kind = 'regular' WHERE debt_kind IS NULL OR debt_kind = ''")

    account_cols = {row[1] for row in conn.execute("PRAGMA table_info(accounts)").fetchall()}
    if "opening_balance" not in account_cols:
        conn.execute("ALTER TABLE accounts ADD COLUMN opening_balance REAL NOT NULL DEFAULT 0")

    conn.commit()
