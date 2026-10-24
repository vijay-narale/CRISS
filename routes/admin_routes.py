"""
Administrative Workspace & Resource Intelligence Routes for CRISS.
Provides role-authorized inventory management, circulation desk, reservation approvals,
Demand-Aware Allocation Engine, maintenance workflows, and CSV analytical reporting.
"""

import csv
import io
from datetime import datetime, timedelta
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, Response
from database.connection import execute_query, execute_statement, get_db_cursor
from services.reservation_service import ReservationService
from services.loan_service import LoanService
from services.demand_engine import DemandEngine
from routes.auth_routes import roles_accepted, validate_csrf, generate_csrf_token

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

@admin_bp.route('/dashboard')
@roles_accepted('admin')
def dashboard():
    # 1. High-level KPI metrics
    kpi = execute_query(
        """SELECT 
               (SELECT COUNT(*) FROM resources WHERE owner_type = 'institution') AS total_resources,
               (SELECT COUNT(*) FROM resource_copies) AS total_copies,
               (SELECT COUNT(*) FROM resource_copies WHERE status = 'available') AS available_copies,
               (SELECT COUNT(*) FROM reservations WHERE status IN ('confirmed', 'pending_approval') AND end_datetime >= NOW()) AS active_reservations,
               (SELECT COUNT(*) FROM reservations WHERE status = 'pending_approval') AS pending_approvals,
               (SELECT COUNT(*) FROM loans WHERE status = 'active') AS active_loans,
               (SELECT COUNT(*) FROM loans WHERE status = 'overdue' OR (status = 'active' AND due_date < NOW())) AS overdue_loans,
               (SELECT COUNT(*) FROM resource_requests WHERE status = 'unfulfilled') AS unfulfilled_requests,
               (SELECT COUNT(*) FROM maintenance_records WHERE status IN ('reported', 'in_repair')) AS maintenance_items;""",
        fetchone=True
    )

    # Calculate overall campus inventory utilization percentage
    total_copies = kpi['total_copies'] or 1
    busy_copies = (kpi['total_copies'] - kpi['available_copies']) if kpi['total_copies'] else 0
    utilization_rate = round((busy_copies / total_copies) * 100.0, 1)

    # 2. Urgent Overdue Loans
    overdue_loans = execute_query(
        """SELECT 
               l.loan_id,
               u.full_name AS borrower_name,
               u.student_faculty_id,
               u.email AS borrower_email,
               r.title AS resource_title,
               rc.barcode,
               l.checkout_date,
               l.due_date,
               DATEDIFF(NOW(), l.due_date) AS days_overdue
           FROM loans l
           INNER JOIN users u ON l.borrower_id = u.user_id
           INNER JOIN resource_copies rc ON l.copy_id = rc.copy_id
           INNER JOIN resources r ON rc.resource_id = r.resource_id
           WHERE l.status = 'overdue' OR (l.status = 'active' AND l.due_date < NOW())
           ORDER BY l.due_date ASC
           LIMIT 5;"""
    )

    # 3. Pending Reservation Approvals
    pending_reservations = execute_query(
        """SELECT 
               res.reservation_id,
               u.full_name AS requester_name,
               u.role AS requester_role,
               r.title AS resource_title,
               rc.barcode,
               res.start_datetime,
               res.end_datetime,
               res.notes
           FROM reservations res
           INNER JOIN users u ON res.user_id = u.user_id
           INNER JOIN resources r ON res.resource_id = r.resource_id
           LEFT JOIN resource_copies rc ON res.copy_id = rc.copy_id
           WHERE res.status = 'pending_approval'
           ORDER BY res.start_datetime ASC
           LIMIT 5;"""
    )

    return render_template(
        'admin/dashboard.html',
        kpi=kpi,
        utilization_rate=utilization_rate,
        overdue_loans=overdue_loans,
        pending_reservations=pending_reservations,
        csrf_token=generate_csrf_token()
    )

@admin_bp.route('/inventory')
@roles_accepted('admin')
def inventory():
    category_id = request.args.get('category')
    dept_id = request.args.get('dept')
    status_filter = request.args.get('status')

    params = []
    where_clauses = ["1=1"]

    if category_id and category_id.isdigit():
        where_clauses.append("r.category_id = %s")
        params.append(int(category_id))

    if dept_id and dept_id.isdigit():
        where_clauses.append("r.department_id = %s")
        params.append(int(dept_id))

    where_sql = " AND ".join(where_clauses)

    resources = execute_query(
        f"""SELECT 
                r.resource_id,
                r.title,
                c.name AS category_name,
                d.code AS dept_code,
                r.location,
                r.requires_approval,
                r.owner_type,
                COUNT(rc.copy_id) AS total_copies,
                SUM(CASE WHEN rc.status = 'available' THEN 1 ELSE 0 END) AS available_copies,
                SUM(CASE WHEN rc.status = 'on_loan' THEN 1 ELSE 0 END) AS on_loan_copies,
                SUM(CASE WHEN rc.status = 'reserved' THEN 1 ELSE 0 END) AS reserved_copies,
                SUM(CASE WHEN rc.status = 'maintenance' THEN 1 ELSE 0 END) AS maintenance_copies
            FROM resources r
            INNER JOIN categories c ON r.category_id = c.category_id
            LEFT JOIN departments d ON r.department_id = d.department_id
            LEFT JOIN resource_copies rc ON r.resource_id = rc.resource_id
            WHERE {where_sql}
            GROUP BY r.resource_id, r.title, c.name, d.code, r.location, r.requires_approval, r.owner_type
            ORDER BY r.title ASC;""",
        params
    )

    # Physical copies list
    copies_sql = """
        SELECT 
            rc.copy_id,
            rc.barcode,
            rc.condition_grade,
            rc.status,
            r.title AS resource_title,
            c.name AS category_name
        FROM resource_copies rc
        INNER JOIN resources r ON rc.resource_id = r.resource_id
        INNER JOIN categories c ON r.category_id = c.category_id
    """
    if status_filter:
        copies_sql += " WHERE rc.status = %s"
        copies = execute_query(copies_sql + " ORDER BY rc.barcode ASC;", (status_filter,))
    else:
        copies = execute_query(copies_sql + " ORDER BY rc.barcode ASC;")

    categories = execute_query("SELECT category_id, name FROM categories ORDER BY name ASC;")
    departments = execute_query("SELECT department_id, name, code FROM departments ORDER BY code ASC;")

    return render_template(
        'admin/inventory.html',
        resources=resources,
        copies=copies,
        categories=categories,
        departments=departments,
        selected_category=category_id,
        selected_dept=dept_id,
        selected_status=status_filter,
        csrf_token=generate_csrf_token()
    )

@admin_bp.route('/inventory/add-resource', methods=['POST'])
@roles_accepted('admin')
def add_resource():
    csrf = request.form.get('csrf_token')
    if not validate_csrf(csrf):
        flash("Invalid security token.", "danger")
        return redirect(url_for('admin.inventory'))

    title = request.form.get('title', '').strip()
    category_id = request.form.get('category_id')
    department_id = request.form.get('department_id')
    isbn_or_identifier = request.form.get('isbn_or_identifier', '').strip()
    model_or_author = request.form.get('model_or_author', '').strip()
    purpose = request.form.get('purpose', '').strip()
    location = request.form.get('location', '').strip()
    requires_approval = True if request.form.get('requires_approval') == '1' else False
    initial_copies = int(request.form.get('initial_copies', 1))

    if not title or not category_id or not location:
        flash("Title, Category, and Location are mandatory.", "warning")
        return redirect(url_for('admin.inventory'))

    with get_db_cursor(commit=True) as (conn, cur):
        cur.execute(
            """INSERT INTO resources 
               (title, category_id, department_id, owner_type, isbn_or_identifier, model_or_author, purpose, location, requires_approval)
               VALUES (%s, %s, %s, 'institution', %s, %s, %s, %s, %s);""",
            (title, int(category_id), int(department_id) if department_id else None,
             isbn_or_identifier or None, model_or_author or None, purpose or None, location, requires_approval)
        )
        res_id = cur.lastrowid

        # Automatically create initial copies if specified
        cat_row = execute_query("SELECT name FROM categories WHERE category_id = %s;", (category_id,), fetchone=True)
        prefix = cat_row['name'][:3].upper() if cat_row else 'RES'
        for i in range(1, initial_copies + 1):
            barcode = f"CRISS-{prefix}-{res_id:03d}-{i:02d}"
            cur.execute(
                "INSERT INTO resource_copies (resource_id, barcode, condition_grade, status) VALUES (%s, %s, 'Good', 'available');",
                (res_id, barcode)
            )

        cur.execute(
            """INSERT INTO usage_logs (entity_type, entity_id, user_id, action, details)
               VALUES ('RESOURCE', %s, %s, 'CREATE_RESOURCE', %s);""",
            (res_id, session['user_id'], f"Admin added resource '{title}' with {initial_copies} copies.")
        )

    flash(f"Resource '{title}' created successfully with {initial_copies} initial unit(s).", "success")
    return redirect(url_for('admin.inventory'))

@admin_bp.route('/inventory/add-copy', methods=['POST'])
@roles_accepted('admin')
def add_copy():
    csrf = request.form.get('csrf_token')
    if not validate_csrf(csrf):
        flash("Invalid security token.", "danger")
        return redirect(url_for('admin.inventory'))

    resource_id = request.form.get('resource_id')
    barcode = request.form.get('barcode', '').strip().upper()
    condition_grade = request.form.get('condition_grade', 'Good')

    if not resource_id or not barcode:
        flash("Resource and Barcode are required.", "warning")
        return redirect(url_for('admin.inventory'))

    existing = execute_query("SELECT copy_id FROM resource_copies WHERE barcode = %s;", (barcode,), fetchone=True)
    if existing:
        flash(f"A copy with barcode '{barcode}' already exists.", "danger")
        return redirect(url_for('admin.inventory'))

    execute_statement(
        "INSERT INTO resource_copies (resource_id, barcode, condition_grade, status) VALUES (%s, %s, %s, 'available');",
        (int(resource_id), barcode, condition_grade)
    )
    flash(f"Physical copy #{barcode} registered successfully.", "success")
    return redirect(url_for('admin.inventory'))

@admin_bp.route('/inventory/copy/<int:copy_id>/update-status', methods=['POST'])
@roles_accepted('admin')
def update_copy_status(copy_id):
    csrf = request.form.get('csrf_token')
    if not validate_csrf(csrf):
        flash("Invalid security token.", "danger")
        return redirect(url_for('admin.inventory'))

    new_status = request.form.get('status')
    if new_status not in ('available', 'reserved', 'on_loan', 'maintenance', 'retired'):
        flash("Invalid status specified.", "warning")
        return redirect(url_for('admin.inventory'))

    execute_statement("UPDATE resource_copies SET status = %s WHERE copy_id = %s;", (new_status, copy_id))
    flash(f"Copy status updated to '{new_status}'.", "info")
    return redirect(url_for('admin.inventory'))

@admin_bp.route('/loans')
@roles_accepted('admin')
def loans():
    # Active & Overdue Loans
    active_loans = execute_query(
        """SELECT 
               l.loan_id,
               u.full_name AS borrower_name,
               u.student_faculty_id,
               u.email AS borrower_email,
               r.title AS resource_title,
               rc.barcode,
               l.checkout_date,
               l.due_date,
               l.status,
               l.checkout_condition,
               DATEDIFF(NOW(), l.due_date) AS days_overdue
           FROM loans l
           INNER JOIN users u ON l.borrower_id = u.user_id
           INNER JOIN resource_copies rc ON l.copy_id = rc.copy_id
           INNER JOIN resources r ON rc.resource_id = r.resource_id
           WHERE l.status IN ('active', 'overdue')
           ORDER BY l.due_date ASC;"""
    )

    # Returned Loan History
    returned_loans = execute_query(
        """SELECT 
               l.loan_id,
               u.full_name AS borrower_name,
               u.student_faculty_id,
               r.title AS resource_title,
               rc.barcode,
               l.checkout_date,
               l.due_date,
               l.return_date,
               l.checkout_condition,
               l.return_condition,
               l.notes
           FROM loans l
           INNER JOIN users u ON l.borrower_id = u.user_id
           INNER JOIN resource_copies rc ON l.copy_id = rc.copy_id
           INNER JOIN resources r ON rc.resource_id = r.resource_id
           WHERE l.status = 'returned'
           ORDER BY l.return_date DESC
           LIMIT 20;"""
    )

    return render_template(
        'admin/loans.html',
        active_loans=active_loans,
        returned_loans=returned_loans,
        csrf_token=generate_csrf_token()
    )

@admin_bp.route('/loans/checkout', methods=['POST'])
@roles_accepted('admin')
def checkout():
    csrf = request.form.get('csrf_token')
    if not validate_csrf(csrf):
        flash("Invalid security token.", "danger")
        return redirect(url_for('admin.loans'))

    barcode = request.form.get('barcode', '').strip()
    identifier = request.form.get('borrower_identifier', '').strip()
    custom_days = request.form.get('custom_days')

    # Resolve borrower by email or Student/Faculty ID
    borrower = execute_query(
        "SELECT user_id, full_name FROM users WHERE email = %s OR student_faculty_id = %s;",
        (identifier.lower(), identifier),
        fetchone=True
    )
    if not borrower:
        flash(f"Borrower with ID/email '{identifier}' was not found in user database.", "danger")
        return redirect(url_for('admin.loans'))

    days_int = int(custom_days) if custom_days and custom_days.isdigit() else None
    res, err = LoanService.checkout_resource(
        barcode=barcode,
        borrower_id=borrower['user_id'],
        issuer_id=session['user_id'],
        custom_days=days_int
    )
    if err:
        flash(f"Checkout rejected: {err}", "danger")
    else:
        flash(f"Checkout successful! '{res['title']}' (#{res['barcode']}) issued to {borrower['full_name']} (Due: {res['due_date'].strftime('%b %d, %Y')}).", "success")

    return redirect(url_for('admin.loans'))

@admin_bp.route('/loans/return', methods=['POST'])
@roles_accepted('admin')
def return_resource():
    csrf = request.form.get('csrf_token')
    if not validate_csrf(csrf):
        flash("Invalid security token.", "danger")
        return redirect(url_for('admin.loans'))

    loan_id = request.form.get('loan_id')
    barcode = request.form.get('barcode', '').strip()
    return_condition = request.form.get('return_condition', 'Good')
    notes = request.form.get('notes', '').strip()

    if not loan_id and barcode:
        # Lookup active loan by copy barcode
        loan_row = execute_query(
            """SELECT l.loan_id FROM loans l 
               INNER JOIN resource_copies rc ON l.copy_id = rc.copy_id 
               WHERE rc.barcode = %s AND l.status IN ('active', 'overdue')
               LIMIT 1;""",
            (barcode,),
            fetchone=True
        )
        if loan_row:
            loan_id = loan_row['loan_id']
        else:
            flash(f"No active loan found for copy barcode '{barcode}'.", "warning")
            return redirect(url_for('admin.loans'))

    if not loan_id:
        flash("Please provide a Loan ID or Copy Barcode.", "warning")
        return redirect(url_for('admin.loans'))

    success, msg = LoanService.return_resource(
        loan_id=int(loan_id),
        return_condition=return_condition,
        notes=notes,
        admin_user_id=session['user_id']
    )
    if success:
        flash(msg, "success")
    else:
        flash(msg, "danger")

    return redirect(url_for('admin.loans'))

@admin_bp.route('/loans/scan-overdue', methods=['POST'])
@roles_accepted('admin')
def scan_overdue():
    csrf = request.form.get('csrf_token')
    if not validate_csrf(csrf):
        flash("Invalid security token.", "danger")
        return redirect(url_for('admin.loans'))

    count = LoanService.scan_and_update_overdue()
    flash(f"Overdue scan complete: {count} active loan(s) flagged overdue and borrower notices dispatched.", "info")
    return redirect(url_for('admin.loans'))

@admin_bp.route('/reservations')
@roles_accepted('admin')
def reservations():
    status_filter = request.args.get('status')
    sql = """
        SELECT 
            res.reservation_id,
            res.resource_id,
            r.title AS resource_title,
            c.name AS category_name,
            rc.barcode,
            u.full_name AS requester_name,
            u.email AS requester_email,
            u.role AS requester_role,
            d.code AS dept_code,
            res.start_datetime,
            res.end_datetime,
            res.status,
            res.notes,
            res.created_at
        FROM reservations res
        INNER JOIN resources r ON res.resource_id = r.resource_id
        INNER JOIN categories c ON r.category_id = c.category_id
        INNER JOIN users u ON res.user_id = u.user_id
        LEFT JOIN departments d ON u.department_id = d.department_id
        LEFT JOIN resource_copies rc ON res.copy_id = rc.copy_id
    """
    if status_filter:
        sql += " WHERE res.status = %s"
        reservations_list = execute_query(sql + " ORDER BY res.start_datetime DESC;", (status_filter,))
    else:
        reservations_list = execute_query(sql + " ORDER BY res.start_datetime DESC;")

    return render_template(
        'admin/reservations.html',
        reservations=reservations_list,
        selected_status=status_filter,
        csrf_token=generate_csrf_token()
    )

@admin_bp.route('/reservations/<int:reservation_id>/review', methods=['POST'])
@roles_accepted('admin')
def review_reservation(reservation_id):
    csrf = request.form.get('csrf_token')
    if not validate_csrf(csrf):
        flash("Invalid security token.", "danger")
        return redirect(url_for('admin.reservations'))

    action = request.form.get('action') # 'approve' or 'reject'
    notes = request.form.get('notes', '').strip()
    approve = (action == 'approve')

    success, msg = ReservationService.approve_reservation(
        reservation_id=reservation_id,
        admin_id=session['user_id'],
        approve=approve,
        notes=notes
    )
    if success:
        flash(msg, "success")
    else:
        flash(msg, "danger")

    return redirect(url_for('admin.reservations'))

@admin_bp.route('/demand-engine')
@roles_accepted('admin')
def demand_engine():
    formula_info = DemandEngine.FORMULA_EXPLANATION
    category_demand = DemandEngine.get_category_unmet_demand()
    ranked_resources = DemandEngine.rank_resources_for_review()

    # Unfulfilled requests queue
    unfulfilled_requests = execute_query(
        """SELECT 
               req.request_id,
               u.full_name AS requester_name,
               u.email AS requester_email,
               r.resource_id,
               r.title AS resource_title,
               c.category_id,
               c.name AS category_name,
               req.description,
               req.created_at,
               (SELECT COUNT(*) FROM resource_copies rc WHERE rc.resource_id = r.resource_id AND rc.status = 'available') AS available_stock_count
           FROM resource_requests req
           INNER JOIN users u ON req.user_id = u.user_id
           INNER JOIN categories c ON req.category_id = c.category_id
           LEFT JOIN resources r ON req.resource_id = r.resource_id
           WHERE req.status = 'unfulfilled'
           ORDER BY req.created_at ASC;"""
    )

    # Available copies list for fulfillment modal
    available_copies = execute_query(
        """SELECT rc.copy_id, rc.barcode, r.title, r.resource_id
           FROM resource_copies rc
           INNER JOIN resources r ON rc.resource_id = r.resource_id
           WHERE rc.status = 'available'
           ORDER BY r.title ASC;"""
    )

    return render_template(
        'admin/demand_engine.html',
        formula_info=formula_info,
        category_demand=category_demand,
        ranked_resources=ranked_resources,
        unfulfilled_requests=unfulfilled_requests,
        available_copies=available_copies,
        csrf_token=generate_csrf_token()
    )

@admin_bp.route('/demand-engine/fulfill', methods=['POST'])
@roles_accepted('admin')
def fulfill_demand_request():
    csrf = request.form.get('csrf_token')
    if not validate_csrf(csrf):
        flash("Invalid security token.", "danger")
        return redirect(url_for('admin.demand_engine'))

    request_id = request.form.get('request_id')
    copy_id = request.form.get('copy_id')

    if not request_id or not copy_id:
        flash("Request ID and Copy ID are required to fulfill stock.", "warning")
        return redirect(url_for('admin.demand_engine'))

    success, msg = DemandEngine.fulfill_request(int(request_id), int(copy_id))
    if success:
        flash(msg, "success")
    else:
        flash(msg, "danger")

    return redirect(url_for('admin.demand_engine'))

@admin_bp.route('/maintenance')
@roles_accepted('admin')
def maintenance():
    records = execute_query(
        """SELECT 
               m.maintenance_id,
               rc.barcode,
               r.title AS resource_title,
               c.name AS category_name,
               u.full_name AS reporter_name,
               m.issue_description,
               m.status,
               m.cost,
               m.started_at,
               m.completed_at,
               m.repair_notes
           FROM maintenance_records m
           INNER JOIN resource_copies rc ON m.copy_id = rc.copy_id
           INNER JOIN resources r ON rc.resource_id = r.resource_id
           INNER JOIN categories c ON r.category_id = c.category_id
           INNER JOIN users u ON m.reported_by = u.user_id
           ORDER BY m.started_at DESC;"""
    )

    # Copies eligible for reporting maintenance
    eligible_copies = execute_query(
        """SELECT rc.copy_id, rc.barcode, r.title 
           FROM resource_copies rc 
           INNER JOIN resources r ON rc.resource_id = r.resource_id
           WHERE rc.status != 'retired'
           ORDER BY r.title ASC;"""
    )

    return render_template(
        'admin/maintenance.html',
        records=records,
        eligible_copies=eligible_copies,
        csrf_token=generate_csrf_token()
    )

@admin_bp.route('/maintenance/create', methods=['POST'])
@roles_accepted('admin')
def create_maintenance_ticket():
    csrf = request.form.get('csrf_token')
    if not validate_csrf(csrf):
        flash("Invalid security token.", "danger")
        return redirect(url_for('admin.maintenance'))

    copy_id = request.form.get('copy_id')
    issue_description = request.form.get('issue_description', '').strip()

    if not copy_id or not issue_description:
        flash("Please select a copy and describe the maintenance issue.", "warning")
        return redirect(url_for('admin.maintenance'))

    with get_db_cursor(commit=True) as (conn, cur):
        cur.execute(
            """INSERT INTO maintenance_records (copy_id, reported_by, issue_description, status)
               VALUES (%s, %s, %s, 'reported');""",
            (int(copy_id), session['user_id'], issue_description)
        )
        cur.execute(
            "UPDATE resource_copies SET status = 'maintenance', condition_grade = 'Needs Maintenance' WHERE copy_id = %s;",
            (int(copy_id),)
        )
    flash("Maintenance ticket created. Copy transitioned to maintenance status.", "success")
    return redirect(url_for('admin.maintenance'))

@admin_bp.route('/maintenance/<int:maintenance_id>/update', methods=['POST'])
@roles_accepted('admin')
def update_maintenance_ticket(maintenance_id):
    csrf = request.form.get('csrf_token')
    if not validate_csrf(csrf):
        flash("Invalid security token.", "danger")
        return redirect(url_for('admin.maintenance'))

    new_status = request.form.get('status')
    cost_str = request.form.get('cost', '0.00')
    repair_notes = request.form.get('repair_notes', '').strip()

    try:
        cost = float(cost_str)
    except ValueError:
        cost = 0.0

    with get_db_cursor(commit=True) as (conn, cur):
        cur.execute("SELECT copy_id FROM maintenance_records WHERE maintenance_id = %s;", (maintenance_id,))
        m = cur.fetchone()
        if not m:
            flash("Maintenance record not found.", "danger")
            return redirect(url_for('admin.maintenance'))

        completed_dt = datetime.now() if new_status in ('repaired', 'decommissioned') else None

        cur.execute(
            """UPDATE maintenance_records 
               SET status = %s, cost = %s, repair_notes = %s, completed_at = %s
               WHERE maintenance_id = %s;""",
            (new_status, cost, repair_notes, completed_dt, maintenance_id)
        )

        # If repaired, restore copy to available
        if new_status == 'repaired':
            cur.execute("UPDATE resource_copies SET status = 'available', condition_grade = 'Good' WHERE copy_id = %s;", (m['copy_id'],))
        elif new_status == 'decommissioned':
            cur.execute("UPDATE resource_copies SET status = 'retired' WHERE copy_id = %s;", (m['copy_id'],))

    flash("Maintenance record updated successfully.", "success")
    return redirect(url_for('admin.maintenance'))

@admin_bp.route('/reports')
@roles_accepted('admin')
def reports():
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')

    # Default to last 30 days if not set
    if not start_date:
        start_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
    if not end_date:
        end_date = datetime.now().strftime("%Y-%m-%d")

    # SQL Report: Category Circulation & Aggregate Utilization
    report_circulation = execute_query(
        """SELECT 
               c.name AS category_name,
               COUNT(DISTINCT r.resource_id) AS titles_count,
               COUNT(rc.copy_id) AS total_inventory_units,
               COUNT(l.loan_id) AS loans_issued,
               SUM(CASE WHEN l.status = 'overdue' THEN 1 ELSE 0 END) AS overdue_count,
               ROUND(AVG(DATEDIFF(IFNULL(l.return_date, NOW()), l.checkout_date)), 1) AS avg_loan_duration_days
           FROM categories c
           LEFT JOIN resources r ON c.category_id = r.category_id
           LEFT JOIN resource_copies rc ON r.resource_id = rc.resource_id
           LEFT JOIN loans l ON rc.copy_id = l.copy_id AND DATE(l.checkout_date) BETWEEN %s AND %s
           GROUP BY c.category_id, c.name
           ORDER BY loans_issued DESC;""",
        (start_date, end_date)
    )

    # Departmental Resource Demand Distribution
    report_dept_demand = execute_query(
        """SELECT 
               d.code AS dept_code,
               d.name AS dept_name,
               COUNT(DISTINCT r.resource_id) AS resources_hosted,
               COUNT(l.loan_id) AS student_loans_count,
               COUNT(req.request_id) AS demand_requests_logged
           FROM departments d
           LEFT JOIN resources r ON d.department_id = r.department_id
           LEFT JOIN users u ON d.department_id = u.department_id
           LEFT JOIN loans l ON u.user_id = l.borrower_id AND DATE(l.checkout_date) BETWEEN %s AND %s
           LEFT JOIN resource_requests req ON u.user_id = req.user_id AND DATE(req.created_at) BETWEEN %s AND %s
           GROUP BY d.department_id, d.code, d.name
           ORDER BY student_loans_count DESC;""",
        (start_date, end_date, start_date, end_date)
    )

    return render_template(
        'admin/reports.html',
        report_circulation=report_circulation,
        report_dept_demand=report_dept_demand,
        start_date=start_date,
        end_date=end_date,
        csrf_token=generate_csrf_token()
    )

@admin_bp.route('/reports/export-csv')
@roles_accepted('admin')
def export_csv():
    start_date = request.args.get('start_date', (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d"))
    end_date = request.args.get('end_date', datetime.now().strftime("%Y-%m-%d"))

    loans_data = execute_query(
        """SELECT 
               l.loan_id,
               r.title AS resource_title,
               c.name AS category_name,
               rc.barcode,
               u.full_name AS borrower_name,
               u.student_faculty_id,
               d.code AS borrower_dept,
               DATE_FORMAT(l.checkout_date, '%Y-%m-%d %H:%i') AS checkout_timestamp,
               DATE_FORMAT(l.due_date, '%Y-%m-%d %H:%i') AS due_timestamp,
               DATE_FORMAT(l.return_date, '%Y-%m-%d %H:%i') AS return_timestamp,
               l.status,
               l.checkout_condition,
               l.return_condition
           FROM loans l
           INNER JOIN resource_copies rc ON l.copy_id = rc.copy_id
           INNER JOIN resources r ON rc.resource_id = r.resource_id
           INNER JOIN categories c ON r.category_id = c.category_id
           INNER JOIN users u ON l.borrower_id = u.user_id
           LEFT JOIN departments d ON u.department_id = d.department_id
           WHERE DATE(l.checkout_date) BETWEEN %s AND %s
           ORDER BY l.checkout_date DESC;""",
        (start_date, end_date)
    )

    si = io.StringIO()
    cw = csv.writer(si)
    cw.writerow([
        "Loan ID", "Resource Title", "Category", "Barcode", "Borrower Name",
        "Campus ID", "Department", "Checkout Time", "Due Time", "Return Time",
        "Status", "Checkout Condition", "Return Condition"
    ])

    for row in loans_data:
        cw.writerow([
            row['loan_id'],
            row['resource_title'],
            row['category_name'],
            row['barcode'],
            row['borrower_name'],
            row['student_faculty_id'],
            row['borrower_dept'] or 'N/A',
            row['checkout_timestamp'],
            row['due_timestamp'],
            row['return_timestamp'] or 'Active/Not Returned',
            row['status'],
            row['checkout_condition'],
            row['return_condition'] or 'N/A'
        ])

    output = si.getvalue()
    filename = f"CRISS_Loan_Circulation_Report_{start_date}_to_{end_date}.csv"
    return Response(
        output,
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment;filename={filename}"}
    )
