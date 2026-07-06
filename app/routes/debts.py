from datetime import date
from flask import Blueprint, request, jsonify, g
from app.db import get_db
from app.services.debt_service import refresh_debt_state

debts_bp = Blueprint('debts', __name__)

@debts_bp.route("/api/debts", methods=["GET"])
def get_debts():
    if not g.user:
        return jsonify({"error": "Unauthorized"}), 401
    db = get_db(g.user["id"])
    rows = db.execute("""
        SELECT d.*, COALESCE(SUM(dp.amount), 0) as total_paid,
               a.name as account_name, pa.name as payment_account_name
        FROM debts d
        LEFT JOIN debt_payments dp ON d.id = dp.debt_id
        LEFT JOIN accounts a ON d.account_id = a.id
        LEFT JOIN accounts pa ON d.payment_account_id = pa.id
        GROUP BY d.id
        ORDER BY d.created_at DESC
    """).fetchall()
    return jsonify([dict(r) for r in rows])

@debts_bp.route("/api/debts", methods=["POST"])
def add_debt():
    if not g.user:
        return jsonify({"error": "Unauthorized"}), 401
    data = request.get_json()
    db = get_db(g.user["id"])
    debt_kind = data.get("debt_kind", "regular")
    if debt_kind not in ("regular", "opening"):
        return jsonify({"error": "Jenis hutang tidak valid"}), 400
    
    # Resolve account_id (default to first account if not specified)
    account_id = data.get("account_id")
    if not account_id:
        first_acc = db.execute("SELECT id FROM accounts LIMIT 1").fetchone()
        account_id = first_acc["id"] if first_acc else None
    
    # Create debt record
    cur = db.execute("""
        INSERT INTO debts (person_name, account_id, debt_kind, amount_total, description)
        VALUES (?, ?, ?, ?, ?)
    """, (data["person_name"], account_id, debt_kind, data["amount_total"], data.get("description", "")))
    debt_id = cur.lastrowid
    
    # Pastikan kategori "Hutang" ada (type: Pengeluaran)
    cat_row = db.execute("SELECT id FROM categories WHERE name = 'Hutang' AND type = 'expense' AND user_id = ?", (g.user["id"],)).fetchone()
    if cat_row:
        cat_id = cat_row['id']
    else:
        cur = db.execute("INSERT INTO categories (name, type, user_id) VALUES ('Hutang', 'expense', ?)", (g.user["id"],))
        cat_id = cur.lastrowid

    # Hutang biasa: auto-create expense transaction. Hutang bawaan: no transaction at creation.
    admin_fee = float(data.get("admin_fee") or 0)
    if debt_kind == "regular" and account_id:
        db.execute("""
            INSERT INTO transactions (category_id, account_id, type, amount, admin_fee, description, date)
            VALUES (?, ?, 'expense', ?, ?, ?, ?)
        """, (cat_id, account_id, data["amount_total"], admin_fee, data.get("description") or data.get("person_name", ""), data.get("date") or date.today().isoformat()))
    
    db.commit()
    return jsonify({"ok": True, "id": debt_id})


@debts_bp.route("/api/debts/<int:debt_id>/pay", methods=["POST"])
def pay_debt(debt_id):
    if not g.user:
        return jsonify({"error": "Unauthorized"}), 401
    data = request.get_json()
    db = get_db(g.user["id"])
    
    # Get debt info
    debt = db.execute("SELECT * FROM debts WHERE id = ?", (debt_id,)).fetchone()
    if not debt:
        db.close()
        return jsonify({"error": "Debt not found"}), 404
    
    payment_account_id = data.get("payment_account_id") or debt["account_id"]

    # Record payment
    db.execute("""
        INSERT INTO debt_payments (debt_id, amount, note, date)
        VALUES (?, ?, ?, ?)
    """, (debt_id, data["amount"], data.get("note", ""), data.get("date") or date.today().isoformat()))
    
    # Flow A: same account → income to that account (pelunasan)
    # Flow B: different account → income to debt account + expense from payment account
    # Pastikan kategori "Hutang" ada
    cat_row = db.execute("SELECT id FROM categories WHERE name = 'Hutang' AND type = 'expense' AND user_id = ?", (g.user["id"],)).fetchone()
    if cat_row:
        cat_id = cat_row['id']
    else:
        cur = db.execute("INSERT INTO categories (name, type, user_id) VALUES ('Hutang', 'expense', ?)", (g.user["id"],))
        cat_id = cur.lastrowid

    admin_fee = float(data.get("admin_fee") or 0)

    if payment_account_id == debt["account_id"]:
        # Hutang bawaan maupun same-account regular debt: kredit ke rekening terkait
        tx_cur = db.execute("""
            INSERT INTO transactions (category_id, account_id, type, amount, admin_fee, description, date)
            VALUES (?, ?, 'income', ?, ?, ?, ?)
        """, (cat_id, debt["account_id"], data["amount"], admin_fee, data.get("note", f"Pelunasan hutang: {debt['person_name']}"), data.get("date") or date.today().isoformat()))
    else:
        # Flow B: catat sebagai 1 transfer tunggal dari rekening pembayaran ke rekening hutang
        tx_cur = db.execute("""
            INSERT INTO transactions (category_id, account_id, to_account_id, type, amount, admin_fee, description, date)
            VALUES (?, ?, ?, 'transfer', ?, ?, ?, ?)
        """, (cat_id, payment_account_id, debt["account_id"], data["amount"], admin_fee, data.get("note", f"Pelunasan hutang: {debt['person_name']}"), data.get("date") or date.today().isoformat()))
    tx_id = tx_cur.lastrowid
    
    # Link payment to created transaction
    payment_row = db.execute("""
        SELECT id FROM debt_payments
        WHERE debt_id = ? AND amount = ? AND date = ?
        ORDER BY id DESC LIMIT 1
    """, (debt_id, data["amount"], data.get("date") or date.today().isoformat())).fetchone()
    if payment_row:
        db.execute("UPDATE debt_payments SET transaction_id = ? WHERE id = ?", (tx_id, payment_row["id"]))
    refresh_debt_state(db, debt_id)
    
    # Update payment_account_id on debt
    db.execute("UPDATE debts SET payment_account_id = ? WHERE id = ?", (payment_account_id, debt_id))
    
    # Update paid amount
    updated = db.execute("""
        SELECT d.amount_total, COALESCE(SUM(dp.amount), 0) as total_paid
        FROM debts d LEFT JOIN debt_payments dp ON d.id = dp.debt_id
        WHERE d.id = ? GROUP BY d.id
    """, (debt_id,)).fetchone()
    if updated and updated["total_paid"] >= updated["amount_total"]:
        db.execute("UPDATE debts SET status = 'paid', amount_paid = ? WHERE id = ?", (updated["total_paid"], debt_id))
    elif updated:
        db.execute("UPDATE debts SET amount_paid = ? WHERE id = ?", (updated["total_paid"], debt_id))
    
    db.commit()
    return jsonify({"ok": True})


@debts_bp.route("/api/debts/<int:debt_id>", methods=["DELETE"])
def delete_debt(debt_id):
    if not g.user:
        return jsonify({"error": "Unauthorized"}), 401
    db = get_db(g.user["id"])
    debt = db.execute("SELECT id, debt_kind FROM debts WHERE id = ?", (debt_id,)).fetchone()
    if not debt:
        db.close()
        return jsonify({"error": "Debt not found"}), 404
    if debt["debt_kind"] == "opening":
        db.close()
        return jsonify({"error": "Hutang bawaan tidak bisa dihapus"}), 400
    payment_rows = db.execute("SELECT transaction_id FROM debt_payments WHERE debt_id = ? AND transaction_id IS NOT NULL", (debt_id,)).fetchall()
    for row in payment_rows:
        db.execute("DELETE FROM transactions WHERE id = ?", (row["transaction_id"],))
    db.execute("DELETE FROM debts WHERE id = ?", (debt_id,))
    db.commit()
    return jsonify({"ok": True})
