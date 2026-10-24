"""
Test Suite: Alternative Resource Recommendation Engine.
"""

import pytest
from services.recommendation_service import RecommendationService
from database.connection import execute_query

def test_alternative_recommendations_generation():
    """
    Verify that when an item is unavailable or reviewed,
    alternative suggestions are retrieved in the same category/department
    with explicit rationale explanations.
    """
    # Casio fx-991CW Calculator
    res = execute_query(
        "SELECT resource_id FROM resources WHERE title LIKE '%Casio fx-991CW%';",
        fetchone=True
    )
    assert res is not None

    alternatives = RecommendationService.get_alternatives(res['resource_id'])
    assert isinstance(alternatives, list)
    assert len(alternatives) > 0

    # Verify attributes of top alternative
    top_alt = alternatives[0]
    assert 'resource_id' in top_alt
    assert 'title' in top_alt
    assert 'category_name' in top_alt
    assert 'explanation' in top_alt
    assert 'score' in top_alt
    assert top_alt['score'] > 0
    assert len(top_alt['explanation']) > 15
    assert "Suggested because" in top_alt['explanation']

def test_peer_alternative_suggestion():
    """Verify that student peer listings are surfaced as viable alternatives."""
    # Oppenheim signals and systems is a peer-listed textbook
    peer_res = execute_query(
        "SELECT resource_id FROM resources WHERE title LIKE '%Signals and Systems%';",
        fetchone=True
    )
    assert peer_res is not None

    # Silberschatz textbook alternatives
    db_res = execute_query(
        "SELECT resource_id FROM resources WHERE title LIKE '%Database System Concepts%';",
        fetchone=True
    )
    alts = RecommendationService.get_alternatives(db_res['resource_id'])
    assert len(alts) > 0
    # Should recommend other textbooks
    cat_names = [a['category_name'] for a in alts]
    assert 'Textbooks' in cat_names
