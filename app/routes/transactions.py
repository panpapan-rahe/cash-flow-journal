from flask import Blueprint, request, jsonify, g
from app.db import get_db
from app.services.debt_service import refresh_debt_state
from app.services.transaction_service import create_transaction

transactions_bp = Blueprint('transactions', __name__)

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
    create_transaction(db, data)
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
            from app.services.debt_service import refresh_debt_state
            refresh_debt_state(db, debt_id)

    db.execute("DELETE FROM transactions WHERE id = ?", (tx_id,))
    db.commit()
    return jsonify({"ok": True})
