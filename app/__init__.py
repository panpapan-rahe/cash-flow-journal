import os
from flask import Flask, g, session

from app.routes.auth import auth_bp
from app.routes.pages import pages_bp
from app.routes.transactions import transactions_bp
from app.routes.debts import debts_bp
from app.routes.masterdata import masterdata_bp


def create_app():
    app = Flask(__name__)
    app.secret_key = os.environ.get('SECRET_KEY', 'cashflow-fixed-secret-key-2026')
    app.config.update(
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE='Lax',
        SESSION_COOKIE_SECURE=False,
    )

    @app.teardown_appcontext
    def close_db(exception):
        db = g.pop('db', None)
        if db is not None:
            try:
                db.close()
            except Exception:
                pass

    @app.before_request
    def load_user():
        g.user = None
        if 'user_id' in session:
            g.user = {'id': session['user_id'], 'username': session.get('username', '')}

    app.register_blueprint(auth_bp)
    app.register_blueprint(pages_bp)
    app.register_blueprint(transactions_bp)
    app.register_blueprint(debts_bp)
    app.register_blueprint(masterdata_bp)
    return app
