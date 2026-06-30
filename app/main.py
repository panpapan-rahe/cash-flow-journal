"""Cashflow Web - Main Flask Application."""
import os
from datetime import date
from flask import Flask, request, session, redirect, url_for, render_template, jsonify, flash, g
from werkzeug.security import generate_password_hash, check_password_hash
from app.db import get_db, get_db_path
import sqlite3
from app.models import create_user, authenticate, user_exists, get_user_count, delete_user

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "cashflow-fixed-secret-key-2026")
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='Lax',
    SESSION_COOKIE_SECURE=False
)

# ─── DB Teardown ─────────────────────────────────────────────────
@app.teardown_appcontext
def close_db(exception):
    db = g.pop("db", None)
    if db is not None:
        try:
            db.close()
        except Exception:
            pass

# ─── Debt Helpers ───────────────────────────────────────────────
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

    total_paid = row["total_paid"] or 0
    amount_total = row["amount_total"] or 0
    if total_paid >= amount_total:
        db.execute("UPDATE debts SET status = 'paid', amount_paid = ? WHERE id = ?", (total_paid, debt_id))
    else:
        db.execute("UPDATE debts SET status = 'active', amount_paid = ? WHERE id = ?", (total_paid, debt_id))

@app.before_request
def load_user():
    g.user = None
    if "user_id" in session:
        g.user = {"id": session["user_id"], "username": session.get("username", "")}

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        action = request.form.get("action", "login")

        if action == "register":
            if not username or not password:
                flash("Username dan password wajib diisi.", "error")
            elif user_exists(username):
                flash("Username sudah dipakai.", "error")
            else:
                user_id = create_user(username, password)
                session["user_id"] = user_id
                session["username"] = username
                flash("Akun berhasil dibuat!", "success")
                return redirect(url_for("dashboard"))
        else:
            user = authenticate(username, password)
            if user:
                session["user_id"] = user["id"]
                session["username"] = user["username"]
                return redirect(url_for("dashboard"))
            else:
                flash("Username atau password salah.", "error")

    return render_template("login.html", user_count=get_user_count())

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

# ─── API: User ──────────────────────────────────────────────────
@app.route("/api/user", methods=["DELETE"])
def delete_user_api():
    if not g.user:
        return jsonify({"error": "Unauthorized"}), 401
    user_id = g.user["id"]
    try:
        delete_user(user_id)
    except Exception as e:
        return jsonify({"error": str(e)}), 400
    session.clear()
    return jsonify({"ok": True})

# ─── Protected Routes ───────────────────────────────────────────
@app.route("/")
def index():
    if not g.user:
        return redirect(url_for("login"))
    return redirect(url_for("dashboard"))

@app.route("/dashboard")
def dashboard():
    if not g.user:
        return redirect(url_for("login"))
    db = get_db(g.user["id"])
    row = db.execute("SELECT COUNT(*) AS cnt FROM accounts").fetchone()
    needs_setup = (row["cnt"] == 0)
    return render_template("index.html", username=g.user["username"], needs_setup=needs_setup)

@app.route("/transactions")
def transactions():
    if not g.user:
        return redirect(url_for("login"))
    return render_template("transactions.html", username=g.user["username"])

@app.route("/settings")
def settings():
    if not g.user:
        return redirect(url_for("login"))
    return render_template("settings.html", username=g.user["username"])

# ─── API: Transactions ──────────────────────────────────────────
@app.route("/api/transactions", methods=["GET"])
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

@app.route("/api/transactions", methods=["POST"])
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

@app.route("/api/transactions/<int:tx_id>", methods=["DELETE"])
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

# ─── API: Debts ─────────────────────────────────────────────────
@app.route("/api/debts", methods=["GET"])
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

@app.route("/api/debts", methods=["POST"])
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


@app.route("/api/debts/<int:debt_id>/pay", methods=["POST"])
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


@app.route("/api/debts/<int:debt_id>", methods=["DELETE"])
def delete_debt(debt_id):
    if not g.user:
        return jsonify({"error": "Unauthorized"}), 401
    db = get_db(g.user["id"])
    payment_rows = db.execute("SELECT transaction_id FROM debt_payments WHERE debt_id = ? AND transaction_id IS NOT NULL", (debt_id,)).fetchall()
    for row in payment_rows:
        db.execute("DELETE FROM transactions WHERE id = ?", (row["transaction_id"],))
    db.execute("DELETE FROM debts WHERE id = ?", (debt_id,))
    db.commit()
    return jsonify({"ok": True})


# ─── API: Summary ───────────────────────────────────────────────
@app.route("/api/summary")
def get_summary():
    if not g.user:
        return jsonify({"error": "Unauthorized"}), 401
    db = get_db(g.user["id"])
    
    # Summary: balance = income - expense - transfer_out + transfer_in
    income = db.execute("SELECT COALESCE(SUM(amount), 0) as t FROM transactions WHERE type='income' AND to_account_id IS NULL").fetchone()["t"]
    expense = db.execute("SELECT COALESCE(SUM(amount), 0) as t FROM transactions WHERE type='expense'").fetchone()["t"]
    admin_total = db.execute("SELECT COALESCE(SUM(admin_fee), 0) as t FROM transactions WHERE admin_fee > 0").fetchone()["t"]
    transfer_in = db.execute("SELECT COALESCE(SUM(amount), 0) as t FROM transactions WHERE type='transfer' AND to_account_id IS NOT NULL").fetchone()["t"]
    transfer_out = db.execute("SELECT COALESCE(SUM(amount + COALESCE(admin_fee, 0)), 0) as t FROM transactions WHERE type='transfer' AND account_id IS NOT NULL").fetchone()["t"]
    
    total_debt = db.execute("SELECT COALESCE(SUM(amount_total), 0) as t FROM debts WHERE status='active'").fetchone()["t"]
    total_paid = db.execute("SELECT COALESCE(SUM(amount_paid), 0) as t FROM debts WHERE status='active'").fetchone()["t"]
    
    balance = income - expense - transfer_out + transfer_in
    
    return jsonify({
        "income": income,
        "expense": expense + admin_total,
        "transfer_out": transfer_out,
        "balance": balance,
        "pending_debt": total_debt - total_paid
    })

# ─── API: Categories & Accounts ────────────────────────────────
@app.route("/api/categories")
def get_categories():
    if not g.user:
        return jsonify({"error": "Unauthorized"}), 401
    db = get_db(g.user["id"])
    rows = db.execute("SELECT * FROM categories ORDER BY type, name").fetchall()
    return jsonify([dict(r) for r in rows])

@app.route("/api/accounts/count")
def count_accounts():
    if not g.user:
        return jsonify({"error": "Unauthorized"}), 401
    db = get_db(g.user["id"])
    row = db.execute("SELECT COUNT(*) as cnt FROM accounts").fetchone()
    return jsonify({"count": row["cnt"]})

@app.route("/api/accounts")
def get_accounts():
    if not g.user:
        return jsonify({"error": "Unauthorized"}), 401
    db = get_db(g.user["id"])
    accounts = db.execute("SELECT * FROM accounts ORDER BY name").fetchall()
    
    result = []
    for acc in accounts:
        aid = acc["id"]
        income = db.execute("SELECT COALESCE(SUM(amount), 0) as t FROM transactions WHERE account_id=? AND type='income'", (aid,)).fetchone()["t"]
        expense = db.execute("SELECT COALESCE(SUM(amount + COALESCE(admin_fee, 0)), 0) as t FROM transactions WHERE account_id=? AND type='expense'", (aid,)).fetchone()["t"]
        transfer_out = db.execute("SELECT COALESCE(SUM(amount + COALESCE(admin_fee, 0)), 0) as t FROM transactions WHERE account_id=? AND type='transfer'", (aid,)).fetchone()["t"]
        transfer_in = db.execute("SELECT COALESCE(SUM(amount), 0) as t FROM transactions WHERE to_account_id=? AND type='transfer'", (aid,)).fetchone()["t"]
        
        row = dict(acc)
        row["income"] = income
        row["expense"] = expense
        row["transfer_out"] = transfer_out
        row["transfer_in"] = transfer_in
        row["opening_balance"] = acc["opening_balance"] if acc["opening_balance"] else 0
        row["balance"] = row["opening_balance"] + income - expense - transfer_out + transfer_in
        result.append(row)

    return jsonify(result)

@app.route("/api/accounts", methods=["POST"])
def create_account():
    if not g.user:
        return jsonify({"error": "Unauthorized"}), 401
    data = request.get_json()
    name = data.get("name", "").strip()
    if not name:
        return jsonify({"error": "Nama rekening wajib diisi"}), 400
    opening_balance = float(data.get("opening_balance") or 0)
    db = get_db(g.user["id"])
    try:
        cur = db.execute("INSERT INTO accounts (name, opening_balance) VALUES (?, ?)", (name, opening_balance))
        db.commit()
    except Exception as e:
        db.close()
        return jsonify({"error": str(e)}), 400
    return jsonify({"ok": True, "id": cur.lastrowid})

@app.route("/api/accounts/<int:acc_id>", methods=["PUT"])
def update_account(acc_id):
    if not g.user:
        return jsonify({"error": "Unauthorized"}), 401
    data = request.get_json()
    name = data.get("name", "").strip()
    if not name:
        return jsonify({"error": "Nama rekening wajib diisi"}), 400
    db = get_db(g.user["id"])
    opening_balance = float(data.get("opening_balance") or 0)
    db.execute("UPDATE accounts SET name = ?, opening_balance = ? WHERE id = ?", (name, opening_balance, acc_id))
    db.commit()
    return jsonify({"ok": True})

@app.route("/api/accounts/<int:acc_id>", methods=["DELETE"])
def delete_account(acc_id):
    if not g.user:
        return jsonify({"error": "Unauthorized"}), 401
    db = get_db(g.user["id"])
    db.execute("DELETE FROM accounts WHERE id = ?", (acc_id,))
    db.commit()
    return jsonify({"ok": True})

# ─── API: Categories CRUD ───────────────────────────────────────
@app.route("/api/categories", methods=["POST"])
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

@app.route("/api/categories/<int:cat_id>", methods=["DELETE"])
def delete_category(cat_id):
    if not g.user:
        return jsonify({"error": "Unauthorized"}), 401
    db = get_db(g.user["id"])
    db.execute("DELETE FROM categories WHERE id = ?", (cat_id,))
    db.commit()
    return jsonify({"ok": True})

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=8000)
