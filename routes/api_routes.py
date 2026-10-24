"""
REST API Endpoints for Chart.js and Dynamic Frontend Interaction in CRISS.
"""

from flask import Blueprint, jsonify, session
from database.connection import execute_query
from services.notification_service import NotificationService

api_bp = Blueprint('api', __name__, url_prefix='/api')

@api_bp.route('/stats/utilization-by-category')
def utilization_by_category():
    """Returns category utilization data for Chart.js bar chart."""
    sql = """
        SELECT 
            c.name AS category_name,
            COUNT(rc.copy_id) AS total_units,
            SUM(CASE WHEN rc.status IN ('on_loan', 'reserved') THEN 1 ELSE 0 END) AS active_units,
            ROUND(
                (SUM(CASE WHEN rc.status IN ('on_loan', 'reserved') THEN 1 ELSE 0 END) * 100.0) /
                NULLIF(COUNT(rc.copy_id), 0), 1
            ) AS utilization_pct
        FROM categories c
        LEFT JOIN resources r ON c.category_id = r.category_id
        LEFT JOIN resource_copies rc ON r.resource_id = rc.resource_id
        GROUP BY c.category_id, c.name
        ORDER BY c.name ASC;
    """
    rows = execute_query(sql)
    labels = [r['category_name'] for r in rows]
    total_data = [int(r['total_units'] or 0) for r in rows]
    active_data = [int(r['active_units'] or 0) for r in rows]
    util_data = [float(r['utilization_pct'] or 0.0) for r in rows]

    return jsonify({
        "labels": labels,
        "total": total_data,
        "active": active_data,
        "utilization_pct": util_data
    })

@api_bp.route('/stats/unmet-demand')
def unmet_demand():
    """Returns category unmet demand rates from database view for Chart.js."""
    sql = """
        SELECT 
            category_name,
            total_requests,
            unfulfilled_requests,
            fulfilled_requests,
            IFNULL(unmet_demand_rate_pct, 0.0) AS unmet_demand_rate_pct
        FROM view_unmet_demand_analytics
        ORDER BY category_name ASC;
    """
    rows = execute_query(sql)
    labels = [r['category_name'] for r in rows]
    unfulfilled = [int(r['unfulfilled_requests'] or 0) for r in rows]
    fulfilled = [int(r['fulfilled_requests'] or 0) for r in rows]
    rates = [float(r['unmet_demand_rate_pct'] or 0.0) for r in rows]

    return jsonify({
        "labels": labels,
        "unfulfilled": unfulfilled,
        "fulfilled": fulfilled,
        "rates": rates
    })

@api_bp.route('/stats/inventory-breakdown')
def inventory_breakdown():
    """Returns physical inventory status distribution for pie chart."""
    sql = """
        SELECT 
            status,
            COUNT(*) AS count
        FROM resource_copies
        GROUP BY status;
    """
    rows = execute_query(sql)
    return jsonify({
        "data": {r['status']: r['count'] for r in rows}
    })

@api_bp.route('/notifications/unread-count')
def unread_count():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({"unread_count": 0})
    count = NotificationService.get_unread_count(user_id)
    return jsonify({"unread_count": count})

@api_bp.route('/notifications/mark-read/<int:notif_id>', methods=['POST'])
def mark_read(notif_id):
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({"success": False, "error": "Not authenticated."}), 401
    NotificationService.mark_as_read(notif_id, user_id)
    return jsonify({"success": True})
