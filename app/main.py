"""Cashflow Web - Main Flask Application."""
import os
from flask import Flask, request, session, redirect, url_for, render_template, jsonify, flash, g
from werkzeug.security import generate_password_hash, check_password_hash
from app.db import get_db
from app.models import create_user, authenticate, user_exists, get_user_count

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "cashflow-secret-key-change-in-production")

# ─── Auth Middleware ─────────────────────────────────────────────
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
    return render_template("index.html", username=g.user["username"])

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
    db.close()
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

    # Auto-create account if new
    acc_name = data.get("account", "Utama").strip()
    acc_id = None
    existing_acc = db.execute("SELECT id FROM accounts WHERE name = ?", (acc_name,)).fetchone()
    if existing_acc:
        acc_id = existing_acc["id"]
    else:
        cur = db.execute("INSERT INTO accounts (name) VALUES (?)", (acc_name,))
        acc_id = cur.lastrowid

    to_acc_id = None
    if data.get("type") == "transfer":
        to_name = data.get("to_account", "Lainnya").strip()
        existing_to = db.execute("SELECT id FROM accounts WHERE name = ?", (to_name,)).fetchone()
        if existing_to:
            to_acc_id = existing_to["id"]
        else:
            cur = db.execute("INSERT INTO accounts (name) VALUES (?)", (to_name,))
            to_acc_id = cur.lastrowid

    db.execute("""
        INSERT INTO transactions (category_id, account_id, to_account_id, type, amount, description, date)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (cat_id, acc_id, to_acc_id, data["type"], data["amount"], data.get("description", ""), data.get("date", "")))
    db.commit()
    db.close()
    return jsonify({"ok": True})

@app.route("/api/transactions/<int:tx_id>", methods=["DELETE"])
def delete_transaction(tx_id):
    if not g.user:
        return jsonify({"error": "Unauthorized"}), 401
    db = get_db(g.user["id"])
    db.execute("DELETE FROM transactions WHERE id = ?", (tx_id,))
    db.commit()
    db.close()
    return jsonify({"ok": True})

# ─── API: Debts ─────────────────────────────────────────────────
@app.route("/api/debts", methods=["GET"])
def get_debts():
    if not g.user:
        return jsonify({"error": "Unauthorized"}), 401
    db = get_db(g.user["id"])
    rows = db.execute("""
        SELECT d.*, COALESCE(SUM(dp.amount), 0) as total_paid
        FROM debts d
        LEFT JOIN debt_payments dp ON d.id = dp.debt_id
        GROUP BY d.id
        ORDER BY d.created_at DESC
    """).fetchall()
    db.close()
    return jsonify([dict(r) for r in rows])

@app.route("/api/debts", methods=["POST"])
def add_debt():
    if not g.user:
        return jsonify({"error": "Unauthorized"}), 401
    data = request.get_json()
    db = get_db(g.user["id"])
    db.execute("""
        INSERT INTO debts (person_name, amount_total, description)
        VALUES (?, ?, ?)
    """, (data["person_name"], data["amount_total"], data.get("description", "")))
    db.commit()
    db.close()
    return jsonify({"ok": True})

@app.route("/api/debts/<int:debt_id>/pay", methods=["POST"])
def pay_debt(debt_id):
    if not g.user:
        return jsonify({"error": "Unauthorized"}), 401
    data = request.get_json()
    db = get_db(g.user["id"])
    db.execute("""
        INSERT INTO debt_payments (debt_id, amount, note, date)
        VALUES (?, ?, ?, ?)
    """, (debt_id, data["amount"], data.get("note", ""), data.get("date", "")))
    
    # Update paid amount
    debt = db.execute("""
        SELECT d.amount_total, COALESCE(SUM(dp.amount), 0) as total_paid
        FROM debts d LEFT JOIN debt_payments dp ON d.id = dp.debt_id
        WHERE d.id = ? GROUP BY d.id
    """, (debt_id,)).fetchone()
    if debt and debt["total_paid"] >= debt["amount_total"]:
        db.execute("UPDATE debts SET status = 'paid', amount_paid = ? WHERE id = ?", (debt["total_paid"], debt_id))
    elif debt:
        db.execute("UPDATE debts SET amount_paid = ? WHERE id = ?", (debt["total_paid"], debt_id))
    
    db.commit()
    db.close()
    return jsonify({"ok": True})

@app.route("/api/debts/<int:debt_id>", methods=["DELETE"])
def delete_debt(debt_id):
    if not g.user:
        return jsonify({"error": "Unauthorized"}), 401
    db = get_db(g.user["id"])
    db.execute("DELETE FROM debts WHERE id = ?", (debt_id,))
    db.commit()
    db.close()
    return jsonify({"ok": True})

# ─── API: Summary ───────────────────────────────────────────────
@app.route("/api/summary")
def get_summary():
    if not g.user:
        return jsonify({"error": "Unauthorized"}), 401
    db = get_db(g.user["id"])
    
    income = db.execute("SELECT COALESCE(SUM(amount), 0) as total FROM transactions WHERE type='income'").fetchone()["total"]
    expense = db.execute("SELECT COALESCE(SUM(amount), 0) as total FROM transactions WHERE type='expense'").fetchone()["total"]
    transfer_out = db.execute("SELECT COALESCE(SUM(amount), 0) as total FROM transactions WHERE type='transfer'").fetchone()["total"]
    
    total_debt = db.execute("SELECT COALESCE(SUM(amount_total), 0) as total FROM debts WHERE status='active'").fetchone()["total"]
    total_paid = db.execute("SELECT COALESCE(SUM(amount_paid), 0) as total FROM debts WHERE status='active'").fetchone()["total"]
    
    db.close()
    return jsonify({
        "income": income,
        "expense": expense,
        "transfer_out": transfer_out,
        "balance": income - expense - transfer_out,
        "pending_debt": total_debt - total_paid
    })

# ─── API: Categories & Accounts ────────────────────────────────
@app.route("/api/categories")
def get_categories():
    if not g.user:
        return jsonify({"error": "Unauthorized"}), 401
    db = get_db(g.user["id"])
    rows = db.execute("SELECT * FROM categories ORDER BY type, name").fetchall()
    db.close()
    return jsonify([dict(r) for r in rows])

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
        expense = db.execute("SELECT COALESCE(SUM(amount), 0) as t FROM transactions WHERE account_id=? AND type='expense'", (aid,)).fetchone()["t"]
        transfer_out = db.execute("SELECT COALESCE(SUM(amount), 0) as t FROM transactions WHERE account_id=? AND type='transfer'", (aid,)).fetchone()["t"]
        transfer_in = db.execute("SELECT COALESCE(SUM(amount), 0) as t FROM transactions WHERE to_account_id=? AND type='transfer'", (aid,)).fetchone()["t"]
        
        row = dict(acc)
        row["income"] = income
        row["expense"] = expense
        row["transfer_out"] = transfer_out
        row["transfer_in"] = transfer_in
        row["balance"] = income - expense - transfer_out + transfer_in
        result.append(row)
    
    db.close()
    return jsonify(result)

@app.route("/api/accounts", methods=["POST"])
def create_account():
    if not g.user:
        return jsonify({"error": "Unauthorized"}), 401
    data = request.get_json()
    name = data.get("name", "").strip()
    if not name:
        return jsonify({"error": "Nama rekening wajib diisi"}), 400
    db = get_db(g.user["id"])
    try:
        db.execute("INSERT INTO accounts (name) VALUES (?)", (name,))
        db.commit()
    except Exception as e:
        db.close()
        return jsonify({"error": str(e)}), 400
    db.close()
    return jsonify({"ok": True})

@app.route("/api/accounts/<int:acc_id>", methods=["PUT"])
def update_account(acc_id):
    if not g.user:
        return jsonify({"error": "Unauthorized"}), 401
    data = request.get_json()
    name = data.get("name", "").strip()
    if not name:
        return jsonify({"error": "Nama rekening wajib diisi"}), 400
    db = get_db(g.user["id"])
    db.execute("UPDATE accounts SET name = ? WHERE id = ?", (name, acc_id))
    db.commit()
    db.close()
    return jsonify({"ok": True})

@app.route("/api/accounts/<int:acc_id>", methods=["DELETE"])
def delete_account(acc_id):
    if not g.user:
        return jsonify({"error": "Unauthorized"}), 401
    db = get_db(g.user["id"])
    db.execute("DELETE FROM accounts WHERE id = ?", (acc_id,))
    db.commit()
    db.close()
    return jsonify({"ok": True})

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=8000)
