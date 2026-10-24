"""
Alternative Resource Recommendation Service for CRISS.
Provides rule-based, interpretable alternative suggestions when a requested
asset is unavailable, matching by category, purpose, department, and live stock.
"""

from database.connection import execute_query

class RecommendationService:
    @staticmethod
    def get_alternatives(resource_id):
        """
        Suggests substitute resources when target resource has zero available copies.
        Returns scored alternatives with human-readable rationale explanations.
        """
        # 1. Fetch target resource metadata
        target = execute_query(
            """SELECT r.resource_id, r.title, r.category_id, r.department_id, 
                      r.purpose, c.name AS category_name, d.code AS dept_code
               FROM resources r
               INNER JOIN categories c ON r.category_id = c.category_id
               LEFT JOIN departments d ON r.department_id = d.department_id
               WHERE r.resource_id = %s;""",
            (resource_id,),
            fetchone=True
        )
        if not target:
            return []

        # 2. Extract purpose keywords for relevance scoring
        target_purpose = (target['purpose'] or '').lower()
        purpose_keywords = {w.strip(".,;:()") for w in target_purpose.split() if len(w) > 3}

        # 3. Query candidate alternatives in the same category or department that have available units
        candidates_sql = """
            SELECT 
                r.resource_id,
                r.title,
                r.category_id,
                r.department_id,
                r.purpose,
                r.location,
                r.owner_type,
                c.name AS category_name,
                d.code AS dept_code,
                d.name AS dept_name,
                COUNT(rc.copy_id) AS total_copies,
                SUM(CASE WHEN rc.status = 'available' THEN 1 ELSE 0 END) AS available_copies,
                sl.listing_id,
                sl.condition_desc,
                sl.pickup_instructions
            FROM resources r
            INNER JOIN categories c ON r.category_id = c.category_id
            LEFT JOIN departments d ON r.department_id = d.department_id
            LEFT JOIN resource_copies rc ON r.resource_id = rc.resource_id
            LEFT JOIN student_listings sl ON r.resource_id = sl.resource_id AND sl.listing_status = 'available'
            WHERE r.resource_id != %s
              AND (r.category_id = %s OR r.department_id = %s)
            GROUP BY r.resource_id, r.title, r.category_id, r.department_id, r.purpose, 
                     r.location, r.owner_type, c.name, d.code, d.name, 
                     sl.listing_id, sl.condition_desc, sl.pickup_instructions
            HAVING available_copies > 0 OR sl.listing_id IS NOT NULL;
        """
        candidates = execute_query(
            candidates_sql,
            (resource_id, target['category_id'], target['department_id'])
        )

        recommendations = []
        for cand in candidates:
            score = 0
            reasons = []

            # A. Category match
            if cand['category_id'] == target['category_id']:
                score += 40
                reasons.append(f"Same academic category ({cand['category_name']})")

            # B. Department match
            if cand['department_id'] and cand['department_id'] == target['department_id']:
                score += 25
                reasons.append(f"Located in same department ({cand['dept_code']})")

            # C. Purpose / functional keyword overlap
            cand_purpose = (cand['purpose'] or '').lower()
            overlap = [w for w in purpose_keywords if w in cand_purpose]
            if overlap:
                score += min(20, len(overlap) * 10)
                reasons.append(f"Common curriculum topics: {', '.join(overlap[:3])}")

            # D. Immediate physical availability
            avail_units = cand['available_copies'] or 0
            if avail_units > 0:
                score += min(15, avail_units * 5)
                reasons.append(f"{avail_units} physical unit(s) immediately available in {cand['location']}")
            elif cand['listing_id']:
                score += 15
                reasons.append(f"Peer student listing available ({cand['condition_desc'][:40]}...)")

            # Formulate human-readable explanation
            explanation = "Suggested because: " + "; ".join(reasons) + "."

            recommendations.append({
                "resource_id": cand['resource_id'],
                "title": cand['title'],
                "category_name": cand['category_name'],
                "department_code": cand['dept_code'],
                "location": cand['location'],
                "available_copies": avail_units,
                "is_peer_listing": bool(cand['listing_id']),
                "peer_pickup": cand['pickup_instructions'] if cand['listing_id'] else None,
                "score": score,
                "explanation": explanation
            })

        recommendations.sort(key=lambda x: x['score'], reverse=True)
        return recommendations[:4] # top 4 suggestions
