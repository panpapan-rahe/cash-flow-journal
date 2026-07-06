from flask import Blueprint, request, jsonify, g
from app.db import get_db
from app.services.account_service import get_account_balances, create_account, update_account, delete_account

masterdata_bp = Blueprint('masterdata', __name__)

@masterdata_bp.route("/api/summary")
def get_summary():
    if not g.user:
        return jsonify({"error": "Unauthorized"}), 401
    db = get_db(g.user["id"])
    income = db.execute("SELECT COALESCE(SUM(amount), 0) as t FROM transactions WHERE type='income' AND to_account_id IS NULL").fetchone()["t"]
    expense = db.execute("SELECT COALESCE(SUM(amount), 0) as t FROM transactions WHERE type='expense'").fetchone()["t"]
    admin_total = db.execute("SELECT COALESCE(SUM(admin_fee), 0) as t FROM transactions WHERE admin_fee > 0").fetchone()["t"]
    transfer_in = db.execute("SELECT COALESCE(SUM(amount), 0) as t FROM transactions WHERE type='transfer' AND to_account_id IS NOT NULL").fetchone()["t"]
    transfer_out = db.execute("SELECT COALESCE(SUM(amount + COALESCE(admin_fee, 0)), 0) as t FROM transactions WHERE type='transfer' AND account_id IS NOT NULL").fetchone()["t"]
    total_debt = db.execute("SELECT COALESCE(SUM(amount_total), 0) as t FROM debts WHERE status='active'").fetchone()["t"]
    total_paid = db.execute("SELECT COALESCE(SUM(amount_paid), 0) as t FROM debts WHERE status='active'").fetchone()["t"]
    balance = income - expense - transfer_out + transfer_in
    return jsonify({"income": income, "expense": expense + admin_total, "transfer_out": transfer_out, "balance": balance, "pending_debt": total_debt - total_paid})

@masterdata_bp.route("/api/categories")
def get_categories():
    if not g.user:
        return jsonify({"error": "Unauthorized"}), 401
    db = get_db(g.user["id"])
    rows = db.execute("SELECT * FROM categories ORDER BY type, name").fetchall()
    return jsonify([dict(r) for r in rows])

@masterdata_bp.route("/api/accounts/count")
def count_accounts():
    if not g.user:
        return jsonify({"error": "Unauthorized"}), 401
    db = get_db(g.user["id"])
    row = db.execute("SELECT COUNT(*) as cnt FROM accounts").fetchone()
    return jsonify({"count": row["cnt"]})

@masterdata_bp.route("/api/accounts")
def get_accounts():
    if not g.user:
        return jsonify({"error": "Unauthorized"}), 401
    db = get_db(g.user["id"])
    return jsonify(get_account_balances(db))

@masterdata_bp.route("/api/accounts", methods=["POST"])
def create_account_route():
    if not g.user:
        return jsonify({"error": "Unauthorized"}), 401
    data = request.get_json()
    name = data.get("name", "").strip()
    if not name:
        return jsonify({"error": "Nama rekening wajib diisi"}), 400
    opening_balance = float(data.get("opening_balance") or 0)
    db = get_db(g.user["id"])
    try:
        acc_id = create_account(db, name, opening_balance)
    except Exception as e:
        db.close()
        return jsonify({"error": str(e)}), 400
    return jsonify({"ok": True, "id": acc_id})

@masterdata_bp.route("/api/accounts/<int:acc_id>", methods=["PUT"])
def update_account_route(acc_id):
    if not g.user:
        return jsonify({"error": "Unauthorized"}), 401
    data = request.get_json()
    name = data.get("name", "").strip()
    if not name:
        return jsonify({"error": "Nama rekening wajib diisi"}), 400
    opening_balance = float(data.get("opening_balance") or 0)
    db = get_db(g.user["id"])
    update_account(db, acc_id, name, opening_balance)
    return jsonify({"ok": True})

@masterdata_bp.route("/api/accounts/<int:acc_id>", methods=["DELETE"])
def delete_account_route(acc_id):
    if not g.user:
        return jsonify({"error": "Unauthorized"}), 401
    db = get_db(g.user["id"])
    delete_account(db, acc_id)
    return jsonify({"ok": True})

@masterdata_bp.route("/api/categories", methods=["POST"])
def create_category():
    if not g.user:
        return jsonify({"error": "Unauthorized"}), 401
    data = request.get_json()
    name = data.get("name", "").strip()
    cat_type = data.get("type", "")
    if not name or cat_type not in ("income", "expense"):
        return jsonify({"error": "Nama dan tipe kategori wajib diisi"}), 400
    db = get_db(g.user["id"])
    try:
        db.execute("INSERT INTO categories (name, type) VALUES (?, ?)", (name, cat_type))
        db.commit()
    except Exception as e:
        db.close()
        return jsonify({"error": str(e)}), 400
    return jsonify({"ok": True})

@masterdata_bp.route("/api/categories/<int:cat_id>", methods=["DELETE"])
def delete_category(cat_id):
    if not g.user:
        return jsonify({"error": "Unauthorized"}), 401
    db = get_db(g.user["id"])
    db.execute("DELETE FROM categories WHERE id = ?", (cat_id,))
    db.commit()
    return jsonify({"ok": True})
