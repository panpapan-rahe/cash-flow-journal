from flask import g
from app.db import get_db

def get_account_balances(db):
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
    return result

def create_account(db, name, opening_balance):
    cur = db.execute("INSERT INTO accounts (name, opening_balance) VALUES (?, ?)", (name, opening_balance))
    db.commit()
    return cur.lastrowid

def update_account(db, acc_id, name, opening_balance):
    db.execute("UPDATE accounts SET name = ?, opening_balance = ? WHERE id = ?", (name, opening_balance, acc_id))
    db.commit()

def delete_account(db, acc_id):
    db.execute("DELETE FROM accounts WHERE id = ?", (acc_id,))
    db.commit()
