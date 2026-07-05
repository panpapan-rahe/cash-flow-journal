from flask import Blueprint, redirect, url_for, render_template, g

from app.db import get_db

pages_bp = Blueprint('pages', __name__)


@pages_bp.route('/')
def index():
    if not g.user:
        return redirect(url_for('auth.login'))
    return redirect(url_for('pages.dashboard'))


@pages_bp.route('/dashboard')
def dashboard():
    if not g.user:
        return redirect(url_for('auth.login'))
    db = get_db(g.user['id'])
    row = db.execute('SELECT COUNT(*) AS cnt FROM accounts').fetchone()
    needs_setup = (row['cnt'] == 0)
    return render_template('dashboard/dashboard.html', username=g.user['username'], needs_setup=needs_setup)


@pages_bp.route('/transactions')
def transactions():
    if not g.user:
        return redirect(url_for('auth.login'))
    return render_template('transactions/transactions.html', username=g.user['username'])


@pages_bp.route('/settings')
def settings():
    if not g.user:
        return redirect(url_for('auth.login'))
    return render_template('tools/settings.html', username=g.user['username'])
