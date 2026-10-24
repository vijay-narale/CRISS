"""
Test Suite: Demand-Aware Resource Allocation Engine and Priority Scoring.
"""

import pytest
from services.demand_engine import DemandEngine
from database.connection import execute_query

def test_unmet_demand_calculation_from_view():
    """
    Verify that unmet demand rate equals (unfulfilled / total_valid) * 100
    using the compiled database view 'view_unmet_demand_analytics'.
    """
    category_demand = DemandEngine.get_category_unmet_demand()
    assert len(category_demand) > 0

    for cat in category_demand:
        total = float(cat['total_requests'] or 0)
        unfulfilled = float(cat['unfulfilled_requests'] or 0)
        rate = float(cat['unmet_demand_rate_pct'] or 0)
        if total > 0:
            expected_rate = round((unfulfilled / total) * 100.0, 2)
            assert abs(rate - expected_rate) < 0.05
        else:
            assert rate == 0.0

def test_ranked_resources_priority_scores():
    """Verify that resource ranking produces sorted priorities with formula breakdown."""
    ranked = DemandEngine.rank_resources_for_review()
    assert len(ranked) > 0

    # Ensure list is descending by priority score
    for i in range(len(ranked) - 1):
        assert ranked[i]['priority_score'] >= ranked[i + 1]['priority_score']

    # Verify score components for the top ranked item
    top = ranked[0]
    assert 0 <= top['priority_score'] <= 100
    assert top['priority_tier'] in ('CRITICAL', 'HIGH', 'MODERATE', 'LOW / SUFFICIENT')
    assert len(top['action_recommendation']) > 5

def test_duplicate_request_prevention():
    """Verify that a user cannot submit multiple duplicate active requests for the same resource."""
    user = execute_query("SELECT user_id FROM users WHERE email = 'student@criss.edu';", fetchone=True)
    res = execute_query("SELECT resource_id, category_id FROM resources WHERE title LIKE '%Modern Operating Systems%';", fetchone=True)

    # First request
    req1, err1 = DemandEngine.record_request(
        user_id=user['user_id'],
        resource_id=res['resource_id'],
        category_id=res['category_id'],
        description="Concurrency chapter reading group"
    )

    # Second identical request attempt while the first is unfulfilled
    req2, err2 = DemandEngine.record_request(
        user_id=user['user_id'],
        resource_id=res['resource_id'],
        category_id=res['category_id'],
        description="Duplicate attempt"
    )

    assert err2 is not None
    assert "already have an active request" in err2.lower()

    # Clean up
    execute_query("DELETE FROM resource_requests WHERE request_id = %s;", (req1,))
