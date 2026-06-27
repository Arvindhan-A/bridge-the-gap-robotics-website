import time
from functools import wraps
from flask import session, flash, redirect, url_for, request, abort

from btg.extensions import db
from btg.models import User

# In-memory rate limit store
_login_attempts = {}


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('user_id'):
            flash('Please log in first.', 'warning')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated


def super_admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('user_id'):
            flash('Please log in first.', 'warning')
            return redirect(url_for('auth.login'))
        user = db.session.get(User, session['user_id'])
        if not user or user.role != 'super_admin':
            if user and user.custom_role and user.custom_role.has_permission('manage_roles'):
                return f(*args, **kwargs)
            flash('Access denied. Super admin privileges required.', 'error')
            return redirect(url_for('dashboard.overview'))
        return f(*args, **kwargs)
    return decorated


def chapter_president_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('user_id'):
            flash('Please log in first.', 'warning')
            return redirect(url_for('auth.login'))
        user = db.session.get(User, session['user_id'])
        if not user or user.role not in ('chapter_president', 'super_admin'):
            if user and user.custom_role and user.custom_role.has_permission('manage_events'):
                return f(*args, **kwargs)
            flash('Access denied.', 'error')
            return redirect(url_for('public.home'))
        return f(*args, **kwargs)
    return decorated


def check_rate_limit(ip):
    now = time.time()
    window = 60
    max_attempts = 5

    if ip in _login_attempts:
        attempts, window_start = _login_attempts[ip]
        if now - window_start > window:
            _login_attempts[ip] = (1, now)
            return True
        if attempts >= max_attempts:
            return False
        _login_attempts[ip] = (attempts + 1, window_start)
    else:
        _login_attempts[ip] = (1, now)
    return True
