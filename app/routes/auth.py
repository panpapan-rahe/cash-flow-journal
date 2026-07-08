from flask import Blueprint, request, session, redirect, url_for, render_template, jsonify, flash, g

from app.models import create_user, authenticate, user_exists, get_user_count, delete_user

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        action = request.form.get('action', 'login')

        if action == 'register':
            if not username or not password:
                flash('Username dan password wajib diisi.', 'error')
            elif user_exists(username):
                flash('Username sudah dipakai.', 'error')
            else:
                user_id = create_user(username, password)
                session['user_id'] = user_id
                session['username'] = username
                session['user_code'] = f'{user_id:04d}_{username}' if user_id else None
                flash('Akun berhasil dibuat!', 'success')
                return redirect(url_for('pages.dashboard'))
        else:
            user = authenticate(username, password)
            if user:
                session['user_id'] = user['id']
                session['username'] = user['username']
                session['user_code'] = user.get('user_code')
                return redirect(url_for('pages.dashboard'))
            flash('Username atau password salah.', 'error')

    return render_template('auth/login.html', user_count=get_user_count())


@auth_bp.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('auth.login'))


@auth_bp.route('/api/user', methods=['DELETE'])
def delete_user_api():
    if not g.user:
        return jsonify({'error': 'Unauthorized'}), 401
    user_id = g.user['id']
    try:
        delete_user(user_id)
    except Exception as e:
        return jsonify({'error': str(e)}), 400
    session.clear()
    return jsonify({'ok': True})
