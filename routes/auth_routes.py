"""
Authentication & Authorization Routes for CRISS.
Includes secure session management, role checks, and CSRF protection.
"""

from functools import wraps
import secrets
from flask import Blueprint, render_template, request, redirect, url_for, session, flash, g
from services.auth_service import AuthService
from database.connection import execute_query

auth_bp = Blueprint('auth', __name__)

class CSRFToken(str):
    def __call__(self):
        return str(self)

def generate_csrf_token():
    if '_csrf_token' not in session:
        session['_csrf_token'] = secrets.token_hex(24)
    return CSRFToken(session['_csrf_token'])

def validate_csrf(token):
    return token and session.get('_csrf_token') == token

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash("Please sign in to access this page.", "warning")
            return redirect(url_for('auth.login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function

def roles_accepted(*roles):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'user_id' not in session:
                flash("Please sign in to access this page.", "warning")
                return redirect(url_for('auth.login', next=request.url))
            if session.get('role') not in roles:
                flash("Access denied: You do not have permission to view that resource.", "danger")
                return render_template('errors/403.html'), 403
            return f(*args, **kwargs)
        return decorated_function
    return decorator

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if 'user_id' in session:
        if session.get('role') == 'admin':
            return redirect(url_for('admin.dashboard'))
        return redirect(url_for('student.dashboard'))

    if request.method == 'POST':
        csrf = request.form.get('csrf_token')
        if not validate_csrf(csrf):
            flash("Security check failed (invalid CSRF token). Please try again.", "danger")
            return redirect(url_for('auth.login'))

        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')

        user, err = AuthService.authenticate(email, password)
        if err:
            flash(err, "danger")
            return render_template('login.html', email=email, csrf_token=generate_csrf_token())

        # Establish secure session
        session.clear()
        session['user_id'] = user['user_id']
        session['email'] = user['email']
        session['full_name'] = user['full_name']
        session['role'] = user['role']
        session['department_name'] = user.get('department_name')
        session['_csrf_token'] = secrets.token_hex(24)
        session.permanent = True

        flash(f"Welcome back, {user['full_name']}!", "success")
        next_url = request.args.get('next')
        if next_url and next_url.startswith('/'):
            return redirect(next_url)

        if user['role'] == 'admin':
            return redirect(url_for('admin.dashboard'))
        return redirect(url_for('student.dashboard'))

    return render_template('login.html', csrf_token=generate_csrf_token())

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if 'user_id' in session:
        return redirect(url_for('catalog.index'))

    departments = execute_query("SELECT department_id, name, code FROM departments ORDER BY name ASC;")

    if request.method == 'POST':
        csrf = request.form.get('csrf_token')
        if not validate_csrf(csrf):
            flash("Security check failed (invalid CSRF token). Please try again.", "danger")
            return redirect(url_for('auth.register'))

        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')
        full_name = request.form.get('full_name', '').strip()
        role = request.form.get('role', 'student')
        department_id = request.form.get('department_id')
        student_faculty_id = request.form.get('student_faculty_id', '').strip()
        phone = request.form.get('phone', '').strip()

        # Server-side validation
        if not email or not password or not full_name or not student_faculty_id:
            flash("Please fill in all required fields.", "warning")
            return render_template('register.html', departments=departments, csrf_token=generate_csrf_token())

        if password != confirm_password:
            flash("Passwords do not match.", "warning")
            return render_template('register.html', departments=departments, csrf_token=generate_csrf_token())

        if len(password) < 6:
            flash("Password must be at least 6 characters long.", "warning")
            return render_template('register.html', departments=departments, csrf_token=generate_csrf_token())

        user_id, err = AuthService.register_user(
            email=email,
            password=password,
            full_name=full_name,
            role=role,
            department_id=int(department_id) if department_id else None,
            student_faculty_id=student_faculty_id,
            phone=phone
        )
        if err:
            flash(err, "danger")
            return render_template('register.html', departments=departments, csrf_token=generate_csrf_token())

        flash("Registration successful! You may now log in with your credentials.", "success")
        return redirect(url_for('auth.login'))

    return render_template('register.html', departments=departments, csrf_token=generate_csrf_token())

@auth_bp.route('/logout')
def logout():
    session.clear()
    flash("You have been signed out safely.", "info")
    return redirect(url_for('catalog.index'))
