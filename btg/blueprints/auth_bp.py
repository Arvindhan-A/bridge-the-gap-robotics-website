from flask import Blueprint, render_template, request, redirect, url_for, flash, session

from btg.extensions import db
from btg.models import User
from btg.auth import check_rate_limit
from btg.config import Config

auth = Blueprint('auth', __name__)


@auth.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        ip = request.remote_addr or 'unknown'
        if not check_rate_limit(ip):
            flash('Too many login attempts. Try again in 60 seconds.', 'error')
            return render_template('login.html')

        credential = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        user = User.query.filter(
            db.or_(User.email == credential, User.username == credential)
        ).first()
        if user and user.check_password(password):
            session['user_id'] = user.id
            session['role'] = user.role
            session['chapter_id'] = user.chapter_id

            if user.must_change_password:
                flash('Please change your password before continuing.', 'warning')
                return redirect(url_for('auth.change_password'))

            flash('Welcome back!', 'success')
            if user.role == 'super_admin':
                return redirect(url_for('admin.dashboard'))
            return redirect(url_for('dashboard.overview'))
        flash('Invalid email or password.', 'error')
    return render_template('login.html')


@auth.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out.', 'info')
    return redirect(url_for('public.home'))


@auth.route('/change-password', methods=['GET', 'POST'])
def change_password():
    user_id = session.get('user_id')
    if not user_id:
        return redirect(url_for('auth.login'))
    user = db.session.get(User, user_id)
    if not user:
        return redirect(url_for('auth.login'))

    if request.method == 'POST':
        current = request.form.get('current_password', '')
        new = request.form.get('new_password', '')
        confirm = request.form.get('confirm_password', '')

        if not user.check_password(current):
            flash('Current password is incorrect.', 'error')
            return render_template('change_password.html')

        if len(new) < 8:
            flash('Password must be at least 8 characters.', 'error')
            return render_template('change_password.html')

        if new != confirm:
            flash('Passwords do not match.', 'error')
            return render_template('change_password.html')

        user.set_password(new)
        db.session.commit()
        flash('Password changed successfully.', 'success')
        if user.role == 'super_admin':
            return redirect(url_for('admin.dashboard'))
        return redirect(url_for('dashboard.overview'))

    return render_template('change_password.html')
