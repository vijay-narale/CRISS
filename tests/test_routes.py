"""
Test Suite: Flask Routes, Blueprint Registration, and Template Rendering.
Ensures all web pages, dashboards, navigation links, and API endpoints load cleanly.
"""

import pytest
from app import create_app
from database.connection import execute_query

@pytest.fixture
def client():
    app = create_app()
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client

def test_public_pages(client):
    """Verify that public catalog and information pages render HTTP 200."""
    res = client.get('/')
    assert res.status_code == 200
    assert b"Campus Resource Intelligence &amp; Sharing System" in res.data or b"CRISS" in res.data

    res_cat = client.get('/catalog')
    assert res_cat.status_code == 200
    assert b"Campus Resource Catalog" in res_cat.data

    res_login = client.get('/login')
    assert res_login.status_code == 200
    assert b"Sign In to CRISS" in res_login.data

    res_reg = client.get('/register')
    assert res_reg.status_code == 200
    assert b"Register Campus Account" in res_reg.data

def test_resource_detail_page(client):
    """Verify that a specific resource detail page renders with copies and recommendations."""
    first_res = execute_query("SELECT resource_id FROM resources LIMIT 1;", fetchone=True)
    assert first_res is not None

    res = client.get(f"/resource/{first_res['resource_id']}")
    assert res.status_code == 200
    assert b"Reserve Resource" in res.data

def test_api_endpoints(client):
    """Verify that JSON stats APIs return valid response structures for Chart.js."""
    r1 = client.get('/api/stats/utilization-by-category')
    assert r1.status_code == 200
    j1 = r1.get_json()
    assert 'labels' in j1
    assert 'utilization_pct' in j1

    r2 = client.get('/api/stats/unmet-demand')
    assert r2.status_code == 200
    j2 = r2.get_json()
    assert 'labels' in j2
    assert 'rates' in j2

    r3 = client.get('/api/stats/inventory-breakdown')
    assert r3.status_code == 200
    j3 = r3.get_json()
    assert 'data' in j3

def test_removed_endpoints_return_404(client):
    """Verify that all removed legacy endpoints return HTTP 404."""
    res_get = client.get('/viva/queries')
    assert res_get.status_code == 404

    res_post = client.post('/viva/execute/1')
    assert res_post.status_code == 404

def test_student_authenticated_views(client):
    """Verify that an authenticated student can access their workspace views."""
    student = execute_query("SELECT user_id, email, full_name, role FROM users WHERE email = 'student@criss.edu';", fetchone=True)

    with client.session_transaction() as sess:
        sess['user_id'] = student['user_id']
        sess['email'] = student['email']
        sess['full_name'] = student['full_name']
        sess['role'] = student['role']

    # Dashboard
    r_dash = client.get('/student/dashboard')
    assert r_dash.status_code == 200
    assert b"Student Resource Workspace" in r_dash.data

    # Reservations
    r_res = client.get('/student/reservations')
    assert r_res.status_code == 200
    assert b"My Resource Reservations" in r_res.data

    # Loans
    r_loans = client.get('/student/loans')
    assert r_loans.status_code == 200
    assert b"My Borrowing" in r_loans.data and b"Circulation Records" in r_loans.data

    # Peer listings
    r_list = client.get('/student/listings')
    assert r_list.status_code == 200
    assert b"My Peer Lending Listings" in r_list.data

    # Peer sharing
    r_share = client.get('/student/peer-sharing')
    assert r_share.status_code == 200
    assert b"Student-to-Student Peer Sharing Network" in r_share.data

def test_admin_authenticated_views(client):
    """Verify that an authenticated administrator can access all management panels."""
    admin = execute_query("SELECT user_id, email, full_name, role FROM users WHERE email = 'admin@criss.edu';", fetchone=True)

    with client.session_transaction() as sess:
        sess['user_id'] = admin['user_id']
        sess['email'] = admin['email']
        sess['full_name'] = admin['full_name']
        sess['role'] = admin['role']

    # Admin Dashboard
    r_dash = client.get('/admin/dashboard')
    assert r_dash.status_code == 200
    assert b"Campus Resource Administrative Center" in r_dash.data

    # Inventory
    r_inv = client.get('/admin/inventory')
    assert r_inv.status_code == 200
    assert b"Inventory" in r_inv.data and b"Physical Copy Control" in r_inv.data

    # Loans Desk
    r_loans = client.get('/admin/loans')
    assert r_loans.status_code == 200
    assert b"Campus Circulation" in r_loans.data and b"Loan Desk" in r_loans.data

    # Reservations Manager
    r_res = client.get('/admin/reservations')
    assert r_res.status_code == 200
    assert b"Campus Reservation Holds" in r_res.data

    # Demand Engine
    r_eng = client.get('/admin/demand-engine')
    assert r_eng.status_code == 200
    assert b"Demand-Aware Resource Allocation Engine" in r_eng.data

    # Maintenance
    r_maint = client.get('/admin/maintenance')
    assert r_maint.status_code == 200
    assert b"Campus Equipment Maintenance Desk" in r_maint.data

    # Reports
    r_rep = client.get('/admin/reports')
    assert r_rep.status_code == 200
    assert b"Circulation Analytics" in r_rep.data

    # CSV Export
    r_csv = client.get('/admin/reports/export-csv')
    assert r_csv.status_code == 200
    assert "text/csv" in r_csv.headers.get("Content-Type", "")
