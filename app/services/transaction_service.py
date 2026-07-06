from datetime import date
from flask import g
from app.db import get_db

def resolve_category(db, cat_name, cat_type):
    if not cat_name:
        return None
    
    cat_name = cat_name.strip()
    existing = db.execute("SELECT id FROM categories WHERE name = ? AND type = ?", (cat_name, cat_type)).fetchone()
    if existing:
        return existing["id"]
    
    cur = db.execute("INSERT INTO categories (name, type) VALUES (?, ?)", (cat_name, cat_type))
    return cur.lastrowid

def resolve_account(db, acc_input):
    if not acc_input:
        first = db.execute("SELECT id FROM accounts LIMIT 1").fetchone()
        return first["id"] if first else None
    
    try:
        acc_int = int(acc_input)
        row = db.execute("SELECT id FROM accounts WHERE id = ?", (acc_int,)).fetchone()
        if row:
            return row["id"]
    except (ValueError, TypeError):
        pass

    row = db.execute("SELECT id FROM accounts WHERE name = ?", (str(acc_input),)).fetchone()
    if row:
        return row["id"]
    
    cur = db.execute("INSERT INTO accounts (name) VALUES (?)", (str(acc_input),))
    return cur.lastrowid

def create_transaction(db, data):
    cat_name = data.get("category", "").strip()
    cat_type = data.get("type", "expense")
    cat_id = resolve_category(db, cat_name, cat_type)

    acc_id = resolve_account(db, data.get("account_id") or data.get("account"))
    
    to_acc_id = None
    if data.get("type") == "transfer":
        to_input = data.get("to_account_id") or data.get("to_account", "Lainnya")
        to_acc_id = resolve_account(db, to_input)

    admin_fee = float(data.get("admin_fee") or 0)
    tx_date = data.get("date") or date.today().isoformat()
    desc = data.get("description", "")

    if data.get("type") == "transfer":
        db.execute("""
            INSERT INTO transactions (category_id, account_id, to_account_id, type, amount, admin_fee, description, date)
            VALUES (?, ?, ?, 'transfer', ?, ?, ?, ?)
        """, (cat_id, acc_id, to_acc_id, data["amount"], admin_fee, desc, tx_date))
    else:
        db.execute("""
            INSERT INTO transactions (category_id, account_id, to_account_id, type, amount, admin_fee, description, date)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (cat_id, acc_id, to_acc_id, data["type"], data["amount"], admin_fee, desc, tx_date))
    
    db.commit()
    return True
