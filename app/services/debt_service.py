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
