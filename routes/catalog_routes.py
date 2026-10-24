"""
Catalog & Public Resource Browsing Routes for CRISS.
Supports multi-attribute search, category filtering, availability detection,
and deep resource exploration with alternative recommendations.
"""

from datetime import datetime, timedelta
from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from database.connection import execute_query
from services.reservation_service import ReservationService
from services.recommendation_service import RecommendationService
from services.demand_engine import DemandEngine
from routes.auth_routes import login_required, validate_csrf, generate_csrf_token

catalog_bp = Blueprint('catalog', __name__)

@catalog_bp.route('/')
def index():
    # Landing page with high-level stats
    stats = execute_query(
        """SELECT 
               (SELECT COUNT(*) FROM resources) AS total_resources,
               (SELECT COUNT(*) FROM resource_copies WHERE status = 'available') AS available_copies,
               (SELECT COUNT(*) FROM loans WHERE status = 'active') AS active_loans,
               (SELECT COUNT(*) FROM student_listings WHERE listing_status = 'available') AS peer_listings;""",
        fetchone=True
    )
    categories = execute_query("SELECT category_id, name, description FROM categories ORDER BY name ASC;")
    featured_resources = execute_query(
        """SELECT r.resource_id, r.title, r.location, r.owner_type, c.name AS category_name, d.code AS dept_code,
                  (SELECT COUNT(*) FROM resource_copies rc WHERE rc.resource_id = r.resource_id AND rc.status = 'available') AS available_count
           FROM resources r
           INNER JOIN categories c ON r.category_id = c.category_id
           LEFT JOIN departments d ON r.department_id = d.department_id
           ORDER BY r.created_at DESC
           LIMIT 6;"""
    )
    return render_template('index.html', stats=stats, categories=categories, featured=featured_resources)

@catalog_bp.route('/catalog')
def browse():
    q = request.args.get('q', '').strip()
    category_id = request.args.get('category')
    dept_id = request.args.get('dept')
    owner_type = request.args.get('owner') # 'all', 'institution', 'student'
    avail_filter = request.args.get('avail') # 'all', 'available_only'

    params = []
    where_clauses = ["1=1"]

    if q:
        where_clauses.append("(r.title LIKE %s OR r.purpose LIKE %s OR r.model_or_author LIKE %s OR r.isbn_or_identifier LIKE %s)")
        q_wild = f"%{q}%"
        params.extend([q_wild, q_wild, q_wild, q_wild])

    if category_id and category_id.isdigit():
        where_clauses.append("r.category_id = %s")
        params.append(int(category_id))

    if dept_id and dept_id.isdigit():
        where_clauses.append("r.department_id = %s")
        params.append(int(dept_id))

    if owner_type in ('institution', 'student'):
        where_clauses.append("r.owner_type = %s")
        params.append(owner_type)

    where_sql = " AND ".join(where_clauses)

    sql = f"""
        SELECT 
            r.resource_id,
            r.title,
            r.owner_type,
            r.model_or_author,
            r.isbn_or_identifier,
            r.purpose,
            r.location,
            r.requires_approval,
            c.name AS category_name,
            c.category_id,
            d.code AS dept_code,
            d.name AS dept_name,
            COUNT(rc.copy_id) AS total_copies,
            SUM(CASE WHEN rc.status = 'available' THEN 1 ELSE 0 END) AS available_copies,
            sl.listing_id,
            sl.listing_status,
            sl.pickup_instructions
        FROM resources r
        INNER JOIN categories c ON r.category_id = c.category_id
        LEFT JOIN departments d ON r.department_id = d.department_id
        LEFT JOIN resource_copies rc ON r.resource_id = rc.resource_id
        LEFT JOIN student_listings sl ON r.resource_id = sl.resource_id
        WHERE {where_sql}
        GROUP BY r.resource_id, r.title, r.owner_type, r.model_or_author, r.isbn_or_identifier,
                 r.purpose, r.location, r.requires_approval, c.name, c.category_id, d.code, d.name,
                 sl.listing_id, sl.listing_status, sl.pickup_instructions
    """

    if avail_filter == 'available_only':
        sql += " HAVING (available_copies > 0 OR (sl.listing_id IS NOT NULL AND sl.listing_status = 'available'))"

    sql += " ORDER BY available_copies DESC, r.title ASC;"

    resources = execute_query(sql, params)
    categories = execute_query("SELECT category_id, name FROM categories ORDER BY name ASC;")
    departments = execute_query("SELECT department_id, name, code FROM departments ORDER BY code ASC;")

    return render_template(
        'catalog.html',
        resources=resources,
        categories=categories,
        departments=departments,
        selected_category=category_id,
        selected_dept=dept_id,
        selected_owner=owner_type,
        selected_avail=avail_filter,
        query=q
    )

@catalog_bp.route('/resource/<int:resource_id>')
def resource_detail(resource_id):
    # Fetch resource details
    resource = execute_query(
        """SELECT 
               r.resource_id,
               r.title,
               r.owner_type,
               r.owner_user_id,
               r.model_or_author,
               r.isbn_or_identifier,
               r.purpose,
               r.location,
               r.requires_approval,
               c.category_id,
               c.name AS category_name,
               c.max_borrow_days,
               d.code AS dept_code,
               d.name AS dept_name,
               d.building AS dept_building
           FROM resources r
           INNER JOIN categories c ON r.category_id = c.category_id
           LEFT JOIN departments d ON r.department_id = d.department_id
           WHERE r.resource_id = %s;""",
        (resource_id,),
        fetchone=True
    )
    if not resource:
        flash("Requested resource was not found.", "warning")
        return redirect(url_for('catalog.browse'))

    # Fetch physical copies
    copies = execute_query(
        """SELECT copy_id, barcode, condition_grade, status 
           FROM resource_copies 
           WHERE resource_id = %s 
           ORDER BY barcode ASC;""",
        (resource_id,)
    )
    available_copies_count = sum(1 for cp in copies if cp['status'] == 'available')

    # Student listing details if peer item
    student_listing = None
    if resource['owner_type'] == 'student':
        student_listing = execute_query(
            """SELECT sl.listing_id, sl.condition_desc, sl.pickup_instructions, 
                      sl.listing_status, sl.available_from, sl.available_until,
                      u.full_name AS lender_name, d.code AS lender_dept
               FROM student_listings sl
               INNER JOIN users u ON sl.lender_user_id = u.user_id
               LEFT JOIN departments d ON u.department_id = d.department_id
               WHERE sl.resource_id = %s;""",
            (resource_id,),
            fetchone=True
        )

    # If inventory is unavailable (or 0 available copies), generate alternative recommendations
    alternatives = []
    if available_copies_count == 0 and not (student_listing and student_listing['listing_status'] == 'available'):
        alternatives = RecommendationService.get_alternatives(resource_id)

    # Active reservations for this resource (anonymized schedule view)
    active_reservations = execute_query(
        """SELECT start_datetime, end_datetime, status 
           FROM reservations 
           WHERE resource_id = %s 
             AND status IN ('confirmed', 'pending_approval')
             AND end_datetime >= NOW()
           ORDER BY start_datetime ASC;""",
        (resource_id,)
    )

    now = datetime.now()
    default_start = (now + timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M")
    default_end = (now + timedelta(days=resource['max_borrow_days'])).strftime("%Y-%m-%dT%H:%M")

    return render_template(
        'resource_detail.html',
        resource=resource,
        copies=copies,
        available_copies_count=available_copies_count,
        student_listing=student_listing,
        alternatives=alternatives,
        active_reservations=active_reservations,
        default_start=default_start,
        default_end=default_end,
        csrf_token=generate_csrf_token()
    )

@catalog_bp.route('/resource/<int:resource_id>/reserve', methods=['POST'])
@login_required
def reserve(resource_id):
    csrf = request.form.get('csrf_token')
    if not validate_csrf(csrf):
        flash("Invalid security token. Please try again.", "danger")
        return redirect(url_for('catalog.resource_detail', resource_id=resource_id))

    user_id = session['user_id']
    start_str = request.form.get('start_datetime')
    end_str = request.form.get('end_datetime')
    notes = request.form.get('notes', '').strip()

    try:
        start_dt = datetime.strptime(start_str, "%Y-%m-%dT%H:%M")
        end_dt = datetime.strptime(end_str, "%Y-%m-%dT%H:%M")
    except (ValueError, TypeError):
        flash("Invalid start or end date/time format.", "danger")
        return redirect(url_for('catalog.resource_detail', resource_id=resource_id))

    res, err = ReservationService.create_reservation(resource_id, user_id, start_dt, end_dt, notes)
    if err:
        flash(f"Reservation could not be completed: {err}", "danger")
    else:
        if res['status'] == 'confirmed':
            flash(f"Success! Confirmed reservation for '{res['resource_title']}' (#{res['copy_barcode']}).", "success")
        else:
            flash(f"Reservation submitted! Awaiting coordinator approval for '{res['resource_title']}'.", "info")
        return redirect(url_for('student.reservations'))

    return redirect(url_for('catalog.resource_detail', resource_id=resource_id))

@catalog_bp.route('/resource/<int:resource_id>/request-demand', methods=['POST'])
@login_required
def request_demand(resource_id):
    csrf = request.form.get('csrf_token')
    if not validate_csrf(csrf):
        flash("Invalid security token. Please try again.", "danger")
        return redirect(url_for('catalog.resource_detail', resource_id=resource_id))

    user_id = session['user_id']
    description = request.form.get('description', '').strip()
    category_id = request.form.get('category_id')

    if not description:
        flash("Please provide a brief reason or coursework requirement for your request.", "warning")
        return redirect(url_for('catalog.resource_detail', resource_id=resource_id))

    req_id, err = DemandEngine.record_request(user_id, resource_id, int(category_id), description)
    if err:
        flash(err, "warning")
    else:
        flash("Your unmet demand request has been logged. The campus allocation engine monitors this queue.", "success")

    return redirect(url_for('catalog.resource_detail', resource_id=resource_id))
