from datetime import date
from flask import Blueprint, request, jsonify, g
from app.db import get_db

transactions_bp = Blueprint('transactions', __name__)

def refresh_debt_state(db, debt_id):
    row = db.execute("""
        SELECT d.amount_total, COALESCE(SUM(dp.amount), 0) as total_paid
        FROM debts d
        LEFT JOIN debt_payments dp ON d.id = dp.debt_id
        WHERE d.id = ?
        GROUP BY d.id
    """, (debt_id,)).fetchone()

    if not row:
        return

    total_paid = row['total_paid'] or 0
    amount_total = row['amount_total'] or 0
    if total_paid >= amount_total:
        db.execute("UPDATE debts SET status = 'paid', amount_paid = ? WHERE id = ?", (total_paid, debt_id))
    else:
        db.execute("UPDATE debts SET status = 'active', amount_paid = ? WHERE id = ?", (total_paid, debt_id))

@transactions_bp.route("/api/transactions", methods=["GET"])
def get_transactions():
    if not g.user:
        return jsonify({"error": "Unauthorized"}), 401
    db = get_db(g.user["id"])
    rows = db.execute("""
        SELECT t.*, c.name as category_name, a.name as account_name, 
               ta.name as to_account_name
        FROM transactions t
        LEFT JOIN categories c ON t.category_id = c.id
        LEFT JOIN accounts a ON t.account_id = a.id
        LEFT JOIN accounts ta ON t.to_account_id = ta.id
        ORDER BY t.date DESC, t.id DESC
        LIMIT 100
    """).fetchall()
    return jsonify([dict(r) for r in rows])

@transactions_bp.route("/api/transactions", methods=["POST"])
def add_transaction():
    if not g.user:
        return jsonify({"error": "Unauthorized"}), 401
    data = request.get_json()
    db = get_db(g.user["id"])
    
    # Auto-create category if new
    cat_name = data.get("category", "").strip()
    cat_type = data.get("type", "expense")
    cat_id = None
    if cat_name:
        existing = db.execute("SELECT id FROM categories WHERE name = ? AND type = ?", (cat_name, cat_type)).fetchone()
        if existing:
            cat_id = existing["id"]
        else:
            cur = db.execute("INSERT INTO categories (name, type) VALUES (?, ?)", (cat_name, cat_type))
            cat_id = cur.lastrowid

    # Resolve account (accept ID or name)
    acc_input = data.get("account_id") or data.get("account")
    acc_id = None
    if acc_input:
        try:
            acc_int = int(acc_input)
            row = db.execute("SELECT id FROM accounts WHERE id = ?", (acc_int,)).fetchone()
            acc_id = row["id"] if row else None
        except (ValueError, TypeError):
            row = db.execute("SELECT id FROM accounts WHERE name = ?", (str(acc_input),)).fetchone()
            if row:
                acc_id = row["id"]
            else:
                cur = db.execute("INSERT INTO accounts (name) VALUES (?)", (str(acc_input),))
                acc_id = cur.lastrowid
    else:
        first = db.execute("SELECT id FROM accounts LIMIT 1").fetchone()
        acc_id = first["id"] if first else None

    to_acc_id = None
    if data.get("type") == "transfer":
        to_input = data.get("to_account_id") or data.get("to_account", "Lainnya")
        if isinstance(to_input, (int, float)):
            row = db.execute("SELECT id FROM accounts WHERE id = ?", (to_input,)).fetchone()
            to_acc_id = row["id"] if row else None
        else:
            row = db.execute("SELECT id FROM accounts WHERE name = ?", (str(to_input),)).fetchone()
            if row:
                to_acc_id = row["id"]
            else:
                cur = db.execute("INSERT INTO accounts (name) VALUES (?)", (str(to_input),))
                to_acc_id = cur.lastrowid

    admin_fee = float(data.get("admin_fee") or 0)
    
    if data.get("type") == "transfer":
        # Mutasi: simpan 1 record transfer tunggal
        db.execute("""
            INSERT INTO transactions (category_id, account_id, to_account_id, type, amount, admin_fee, description, date)
            VALUES (?, ?, ?, 'transfer', ?, ?, ?, ?)
        """, (cat_id, acc_id, to_acc_id, data["amount"], admin_fee, data.get("description", ""), data.get("date") or date.today().isoformat()))
    else:
        # Pengeluaran / Pemasukan biasa (amount = nominal murni, admin_fee terpisah)
        db.execute("""
            INSERT INTO transactions (category_id, account_id, to_account_id, type, amount, admin_fee, description, date)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (cat_id, acc_id, to_acc_id, data["type"], data["amount"], admin_fee, data.get("description", ""), data.get("date") or date.today().isoformat()))
    db.commit()
    return jsonify({"ok": True})

@transactions_bp.route("/api/transactions/<int:tx_id>", methods=["DELETE"])
def delete_transaction(tx_id):
    if not g.user:
        return jsonify({"error": "Unauthorized"}), 401
    db = get_db(g.user["id"])
    tx = db.execute("SELECT * FROM transactions WHERE id = ?", (tx_id,)).fetchone()
    if not tx:
        return jsonify({"error": "Transaction not found"}), 404

    # Jika ini transaksi pelunasan hutang, hapus juga debt payment yang terhubung
    if tx["type"] in ("income", "transfer"):
        payment_row = db.execute("SELECT id, debt_id FROM debt_payments WHERE transaction_id = ?", (tx_id,)).fetchone()
        if payment_row:
            debt_id = payment_row["debt_id"]
            db.execute("DELETE FROM debt_payments WHERE id = ?", (payment_row["id"],))
            refresh_debt_state(db, debt_id)

    db.execute("DELETE FROM transactions WHERE id = ?", (tx_id,))
    db.commit()
    return jsonify({"ok": True})
