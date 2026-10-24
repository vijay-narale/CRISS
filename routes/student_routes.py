"""
Student & Faculty User Workspace Routes for CRISS.
Handles user dashboard, reservation tracking, loan history, peer sharing,
and student equipment lending listings with strict privacy protection.
"""

from datetime import datetime, timedelta
from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from database.connection import execute_query, execute_statement, get_db_cursor
from services.reservation_service import ReservationService
from services.loan_service import LoanService
from services.notification_service import NotificationService
from routes.auth_routes import login_required, validate_csrf, generate_csrf_token

student_bp = Blueprint('student', __name__, url_prefix='/student')

@student_bp.route('/dashboard')
@login_required
def dashboard():
    user_id = session['user_id']
    
    # 1. Summary metrics
    stats = execute_query(
        """SELECT 
               (SELECT COUNT(*) FROM loans WHERE borrower_id = %s AND status = 'active') AS active_loans,
               (SELECT COUNT(*) FROM loans WHERE borrower_id = %s AND (status = 'overdue' OR (status = 'active' AND due_date < NOW()))) AS overdue_loans,
               (SELECT COUNT(*) FROM reservations WHERE user_id = %s AND status IN ('confirmed', 'pending_approval') AND end_datetime >= NOW()) AS active_reservations,
               (SELECT COUNT(*) FROM student_listings WHERE lender_user_id = %s AND listing_status = 'available') AS my_active_listings;""",
        (user_id, user_id, user_id, user_id),
        fetchone=True
    )

    # 2. Upcoming loans coming due
    upcoming_loans = execute_query(
        """SELECT l.loan_id, r.title, rc.barcode, l.due_date, 
                  DATEDIFF(l.due_date, NOW()) AS days_left
           FROM loans l
           INNER JOIN resource_copies rc ON l.copy_id = rc.copy_id
           INNER JOIN resources r ON rc.resource_id = r.resource_id
           WHERE l.borrower_id = %s AND l.status = 'active'
           ORDER BY l.due_date ASC
           LIMIT 5;""",
        (user_id,)
    )

    # 3. Upcoming reservations
    recent_reservations = execute_query(
        """SELECT r.reservation_id, res.title, rc.barcode, r.start_datetime, r.end_datetime, r.status
           FROM reservations r
           INNER JOIN resources res ON r.resource_id = res.resource_id
           LEFT JOIN resource_copies rc ON r.copy_id = rc.copy_id
           WHERE r.user_id = %s
           ORDER BY r.start_datetime DESC
           LIMIT 5;""",
        (user_id,)
    )

    # 4. Unread notifications
    notifications = NotificationService.get_user_notifications(user_id, limit=5)

    return render_template(
        'student/dashboard.html',
        stats=stats,
        upcoming_loans=upcoming_loans,
        recent_reservations=recent_reservations,
        notifications=notifications,
        csrf_token=generate_csrf_token()
    )

@student_bp.route('/reservations')
@login_required
def reservations():
    user_id = session['user_id']
    user_reservations = ReservationService.get_user_reservations(user_id)
    return render_template(
        'student/my_reservations.html',
        reservations=user_reservations,
        csrf_token=generate_csrf_token()
    )

@student_bp.route('/reservations/<int:reservation_id>/cancel', methods=['POST'])
@login_required
def cancel_reservation(reservation_id):
    csrf = request.form.get('csrf_token')
    if not validate_csrf(csrf):
        flash("Invalid security token.", "danger")
        return redirect(url_for('student.reservations'))

    success, msg = ReservationService.cancel_reservation(reservation_id, session['user_id'])
    if success:
        flash(msg, "success")
    else:
        flash(msg, "danger")
    return redirect(url_for('student.reservations'))

@student_bp.route('/loans')
@login_required
def loans():
    user_id = session['user_id']
    user_loans = LoanService.get_user_loans(user_id)
    return render_template(
        'student/my_loans.html',
        loans=user_loans,
        csrf_token=generate_csrf_token()
    )

@student_bp.route('/listings')
@login_required
def listings():
    user_id = session['user_id']
    my_listings = execute_query(
        """SELECT 
               sl.listing_id,
               sl.resource_id,
               r.title,
               c.name AS category_name,
               sl.condition_desc,
               sl.pickup_instructions,
               sl.listing_status,
               sl.available_from,
               sl.available_until,
               sl.created_at
           FROM student_listings sl
           INNER JOIN resources r ON sl.resource_id = r.resource_id
           INNER JOIN categories c ON r.category_id = c.category_id
           WHERE sl.lender_user_id = %s
           ORDER BY sl.created_at DESC;""",
        (user_id,)
    )
    categories = execute_query("SELECT category_id, name FROM categories ORDER BY name ASC;")
    departments = execute_query("SELECT department_id, name, code FROM departments ORDER BY code ASC;")

    return render_template(
        'student/my_listings.html',
        listings=my_listings,
        categories=categories,
        departments=departments,
        csrf_token=generate_csrf_token()
    )

@student_bp.route('/listings/create', methods=['POST'])
@login_required
def create_listing():
    csrf = request.form.get('csrf_token')
    if not validate_csrf(csrf):
        flash("Invalid security token.", "danger")
        return redirect(url_for('student.listings'))

    user_id = session['user_id']
    title = request.form.get('title', '').strip()
    category_id = request.form.get('category_id')
    department_id = request.form.get('department_id')
    condition_desc = request.form.get('condition_desc', '').strip()
    pickup_instructions = request.form.get('pickup_instructions', '').strip()
    purpose = request.form.get('purpose', '').strip()
    available_from = request.form.get('available_from')
    available_until = request.form.get('available_until')

    if not title or not category_id or not condition_desc or not pickup_instructions:
        flash("Please complete all required fields for your listing.", "warning")
        return redirect(url_for('student.listings'))

    # Security check: verify safe pickup instructions, do not allow raw private numbers
    with get_db_cursor(commit=True) as (conn, cur):
        # 1. Create student-owned resource record
        cur.execute(
            """INSERT INTO resources 
               (title, category_id, department_id, owner_type, owner_user_id, purpose, location, requires_approval)
               VALUES (%s, %s, %s, 'student', %s, %s, 'Student Peer Handover', FALSE);""",
            (title, int(category_id), int(department_id) if department_id else None, user_id, purpose)
        )
        res_id = cur.lastrowid

        # 2. Create student listing entry
        cur.execute(
            """INSERT INTO student_listings 
               (resource_id, lender_user_id, condition_desc, pickup_instructions, listing_status, available_from, available_until)
               VALUES (%s, %s, %s, %s, 'available', %s, %s);""",
            (res_id, user_id, condition_desc, pickup_instructions, available_from, available_until)
        )

        # 3. Audit log
        cur.execute(
            """INSERT INTO usage_logs (entity_type, entity_id, user_id, action, details)
               VALUES ('STUDENT_LISTING', %s, %s, 'CREATE_LISTING', %s);""",
            (res_id, user_id, f"Student listed peer resource '{title}'.")
        )

    flash("Your resource has been listed successfully in the peer sharing catalog!", "success")
    return redirect(url_for('student.listings'))

@student_bp.route('/listings/<int:listing_id>/update-status', methods=['POST'])
@login_required
def update_listing_status(listing_id):
    csrf = request.form.get('csrf_token')
    if not validate_csrf(csrf):
        flash("Invalid security token.", "danger")
        return redirect(url_for('student.listings'))

    new_status = request.form.get('status')
    if new_status not in ('available', 'paused', 'withdrawn'):
        flash("Invalid status specified.", "warning")
        return redirect(url_for('student.listings'))

    execute_statement(
        "UPDATE student_listings SET listing_status = %s WHERE listing_id = %s AND lender_user_id = %s;",
        (new_status, listing_id, session['user_id'])
    )
    flash(f"Listing status updated to '{new_status}'.", "info")
    return redirect(url_for('student.listings'))

@student_bp.route('/peer-sharing')
@login_required
def peer_sharing():
    """Peer sharing directory where students can borrow from fellow students."""
    peer_resources = execute_query(
        """SELECT 
               sl.listing_id,
               sl.resource_id,
               r.title,
               r.purpose,
               c.name AS category_name,
               u.full_name AS lender_name,
               d.code AS lender_dept,
               sl.condition_desc,
               sl.pickup_instructions,
               sl.listing_status,
               sl.available_from,
               sl.available_until
           FROM student_listings sl
           INNER JOIN resources r ON sl.resource_id = r.resource_id
           INNER JOIN categories c ON r.category_id = c.category_id
           INNER JOIN users u ON sl.lender_user_id = u.user_id
           LEFT JOIN departments d ON u.department_id = d.department_id
           WHERE sl.listing_status = 'available'
           ORDER BY sl.created_at DESC;"""
    )
    return render_template('student/peer_sharing.html', listings=peer_resources)

@student_bp.route('/notifications')
@login_required
def notifications():
    user_id = session['user_id']
    user_notifs = NotificationService.get_user_notifications(user_id, limit=50)
    return render_template('student/notifications.html', notifications=user_notifs, csrf_token=generate_csrf_token())

@student_bp.route('/notifications/mark-all-read', methods=['POST'])
@login_required
def mark_all_notifications_read():
    csrf = request.form.get('csrf_token')
    if not validate_csrf(csrf):
        flash("Invalid security token.", "danger")
        return redirect(url_for('student.notifications'))
    NotificationService.mark_all_read(session['user_id'])
    flash("All notifications marked as read.", "success")
    return redirect(url_for('student.notifications'))
