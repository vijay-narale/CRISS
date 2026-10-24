"""
Demand-Aware Resource Allocation Engine for CRISS.
Computes deterministic unmet demand rates, inventory contention, and priority scoring.
Transparent mathematical formulas without black-box or unsubstantiated AI claims.
"""

from database.connection import get_db_cursor, execute_query

class DemandEngine:
    FORMULA_EXPLANATION = {
        "formula": "Priority Score = (Unmet Demand Rate * 0.40) + (Utilization Rate * 0.35) + (Request Frequency Factor * 0.15) + (Alternative Scarcity Factor * 0.10)",
        "unmet_demand_rate": "Unmet Demand Rate (%) = (Unfulfilled Valid Requests / Total Valid Requests) * 100",
        "utilization_rate": "Utilization Rate (%) = ((On-Loan Copies + Reserved Copies) / Total Inventory Copies) * 100",
        "request_frequency_factor": "Request Frequency Factor = min(100, Total Valid Requests * 20)",
        "alternative_scarcity_factor": "Alternative Scarcity Factor = max(0, 100 - (Available Alternatives * 25))",
        "methodology": "Deterministic linear multi-criteria decision analysis (MCDA) based on verified database transactions and inventory logs. Excludes cancelled requests to prevent duplicate counting."
    }

    @staticmethod
    def get_category_unmet_demand():
        """Fetches aggregate category-wise unmet demand from database view."""
        return execute_query(
            """SELECT 
                   category_id,
                   category_name,
                   total_requests,
                   unfulfilled_requests,
                   fulfilled_requests,
                   IFNULL(unmet_demand_rate_pct, 0.0) AS unmet_demand_rate_pct
               FROM view_unmet_demand_analytics
               ORDER BY unmet_demand_rate_pct DESC, total_requests DESC;"""
        )

    @staticmethod
    def rank_resources_for_review():
        """
        Ranks all institutional resources for administrative purchase,
        reallocation, or peer sharing recruitment.
        """
        # Fetch resources with copies, active loans, reservations, and request counts
        sql = """
            SELECT 
                r.resource_id,
                r.title,
                r.category_id,
                c.name AS category_name,
                d.code AS dept_code,
                d.name AS dept_name,
                r.location,
                COUNT(rc.copy_id) AS total_copies,
                SUM(CASE WHEN rc.status = 'available' THEN 1 ELSE 0 END) AS available_copies,
                SUM(CASE WHEN rc.status = 'on_loan' THEN 1 ELSE 0 END) AS on_loan_copies,
                SUM(CASE WHEN rc.status = 'reserved' THEN 1 ELSE 0 END) AS reserved_copies,
                SUM(CASE WHEN rc.status = 'maintenance' THEN 1 ELSE 0 END) AS maint_copies,
                (
                    SELECT COUNT(*) 
                    FROM resource_requests req 
                    WHERE req.resource_id = r.resource_id 
                      AND req.status IN ('unfulfilled', 'fulfilled')
                ) AS total_valid_requests,
                (
                    SELECT COUNT(*) 
                    FROM resource_requests req 
                    WHERE req.resource_id = r.resource_id 
                      AND req.status = 'unfulfilled'
                ) AS unfulfilled_requests
            FROM resources r
            INNER JOIN categories c ON r.category_id = c.category_id
            LEFT JOIN departments d ON r.department_id = d.department_id
            LEFT JOIN resource_copies rc ON r.resource_id = rc.resource_id
            WHERE r.owner_type = 'institution'
            GROUP BY r.resource_id, r.title, r.category_id, c.name, d.code, d.name, r.location;
        """
        resources = execute_query(sql)

        # Precalculate available alternative count per category
        cat_alt_map = {}
        for row in resources:
            cat_id = row['category_id']
            cat_alt_map[cat_id] = cat_alt_map.get(cat_id, 0) + (1 if row['available_copies'] > 0 else 0)

        ranked = []
        for row in resources:
            total_copies = int(row['total_copies'] or 0)
            avail_copies = int(row['available_copies'] or 0)
            on_loan = int(row['on_loan_copies'] or 0)
            reserved = int(row['reserved_copies'] or 0)
            total_reqs = int(row['total_valid_requests'] or 0)
            unfulfilled = int(row['unfulfilled_requests'] or 0)

            # 1. Unmet Demand Rate
            if total_reqs > 0:
                unmet_demand_rate = round((float(unfulfilled) / float(total_reqs)) * 100.0, 1)
            else:
                unmet_demand_rate = 0.0

            # 2. Resource Utilization Rate
            if total_copies > 0:
                utilization_rate = round(((float(on_loan + reserved)) / float(total_copies)) * 100.0, 1)
            else:
                utilization_rate = 0.0

            # 3. Available alternatives in same category
            cat_avail_count = cat_alt_map.get(row['category_id'], 0)
            # Subtract this resource if it had available copies
            alternatives_count = max(0, cat_avail_count - (1 if avail_copies > 0 else 0))

            # 4. Normalized factors
            req_freq_factor = min(100.0, float(total_reqs) * 20.0)
            alt_scarcity_factor = max(0.0, 100.0 - (float(alternatives_count) * 25.0))

            # 5. Composite Priority Score
            score = round(
                (unmet_demand_rate * 0.40) +
                (utilization_rate * 0.35) +
                (req_freq_factor * 0.15) +
                (alt_scarcity_factor * 0.10),
                1
            )

            # Categorize priority action
            if score >= 70.0:
                priority_tier = "CRITICAL"
                badge_class = "danger"
                action_recommendation = "Procure additional copies immediately or solicit student peer lending."
            elif score >= 45.0:
                priority_tier = "HIGH"
                badge_class = "warning"
                action_recommendation = "Review allocation, recall overdue units, or shorten maximum loan duration."
            elif score >= 20.0:
                priority_tier = "MODERATE"
                badge_class = "info"
                action_recommendation = "Healthy academic circulation; maintain standard maintenance cycle."
            else:
                priority_tier = "LOW / SUFFICIENT"
                badge_class = "success"
                action_recommendation = "Adequate inventory; consider reassigning underused units to sister departments."

            ranked.append({
                "resource_id": row['resource_id'],
                "title": row['title'],
                "category_name": row['category_name'],
                "dept_code": row['dept_code'],
                "total_copies": total_copies,
                "available_copies": avail_copies,
                "utilization_rate": utilization_rate,
                "total_valid_requests": total_reqs,
                "unfulfilled_requests": unfulfilled,
                "unmet_demand_rate": unmet_demand_rate,
                "available_alternatives": alternatives_count,
                "priority_score": score,
                "priority_tier": priority_tier,
                "badge_class": badge_class,
                "action_recommendation": action_recommendation
            })

        ranked.sort(key=lambda x: x['priority_score'], reverse=True)
        return ranked

    @staticmethod
    def record_request(user_id, resource_id, category_id, description):
        """Records an unfulfilled resource request for demand monitoring."""
        with get_db_cursor(commit=True) as (conn, cur):
            # Check for existing unfulfilled request for this user & resource to avoid duplicate counting
            cur.execute(
                """SELECT request_id FROM resource_requests 
                   WHERE user_id = %s AND resource_id = %s AND status = 'unfulfilled';""",
                (user_id, resource_id)
            )
            existing = cur.fetchone()
            if existing:
                return existing['request_id'], "You already have an active request logged for this resource."

            cur.execute(
                """INSERT INTO resource_requests (user_id, resource_id, category_id, description, status)
                   VALUES (%s, %s, %s, %s, 'unfulfilled');""",
                (user_id, resource_id, category_id, description.strip())
            )
            req_id = cur.lastrowid

            cur.execute(
                """INSERT INTO notifications (user_id, title, message, category)
                   VALUES (%s, %s, %s, 'general');""",
                (user_id, "Demand Request Logged",
                 "Your request has been recorded in the campus allocation queue. You will be notified when inventory arrives.")
            )

            return req_id, None

    @staticmethod
    def fulfill_request(request_id, copy_id):
        """Fulfills an unfulfilled request and notifies the student."""
        with get_db_cursor(commit=True) as (conn, cur):
            cur.execute(
                """SELECT req.request_id, req.user_id, req.status, r.title, rc.barcode
                   FROM resource_requests req
                   LEFT JOIN resources r ON req.resource_id = r.resource_id
                   LEFT JOIN resource_copies rc ON rc.copy_id = %s
                   WHERE req.request_id = %s
                   FOR UPDATE;""",
                (copy_id, request_id)
            )
            req = cur.fetchone()
            if not req:
                return False, "Request not found."

            if req['status'] != 'unfulfilled':
                return False, f"Request is already '{req['status']}'."

            cur.execute(
                """UPDATE resource_requests 
                   SET status = 'fulfilled', fulfilled_copy_id = %s, fulfilled_at = NOW()
                   WHERE request_id = %s;""",
                (copy_id, request_id)
            )

            # Notification to user
            cur.execute(
                """INSERT INTO notifications (user_id, title, message, category)
                   VALUES (%s, %s, %s, 'request_fulfilled');""",
                (req['user_id'], "Resource Stock Allocated!",
                 f"Good news! '{req['title'] or 'Your requested resource'}' (#{req['barcode'] or copy_id}) has become available and is allocated for your pickup.")
            )

            return True, "Request fulfilled and notification sent."
