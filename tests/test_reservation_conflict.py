"""
Test Suite: Reservation Conflicts, Double-Booking Prevention, and ACID Transactions.
"""

from datetime import datetime, timedelta
import pytest
from services.reservation_service import ReservationService
from database.connection import execute_query

def test_successful_reservation():
    """Verify that a valid user can successfully reserve an available resource."""
    # Neha Gupta (no overdue loans) reserving Modern Operating Systems (2 available copies)
    user = execute_query("SELECT user_id FROM users WHERE email = 'neha@criss.edu';", fetchone=True)
    res = execute_query("SELECT resource_id FROM resources WHERE title LIKE '%Modern Operating Systems%';", fetchone=True)

    start_dt = datetime.now() + timedelta(days=10)
    end_dt = datetime.now() + timedelta(days=13)

    result, err = ReservationService.create_reservation(
        resource_id=res['resource_id'],
        user_id=user['user_id'],
        start_dt=start_dt,
        end_dt=end_dt,
        notes="OS concurrency midterm test"
    )

    assert err is None
    assert result is not None
    assert result['reservation_id'] is not None
    assert result['status'] == 'confirmed'

    # Clean up test reservation
    ReservationService.cancel_reservation(result['reservation_id'], user['user_id'])

def test_overdue_user_blocked_from_reservation():
    """Verify that a user with an active overdue loan cannot reserve new resources."""
    # Rohit Verma has an active overdue loan in seed data
    user = execute_query("SELECT user_id FROM users WHERE email = 'rohit@criss.edu';", fetchone=True)
    res = execute_query("SELECT resource_id FROM resources WHERE title LIKE '%Modern Operating Systems%';", fetchone=True)

    start_dt = datetime.now() + timedelta(days=5)
    end_dt = datetime.now() + timedelta(days=7)

    result, err = ReservationService.create_reservation(
        resource_id=res['resource_id'],
        user_id=user['user_id'],
        start_dt=start_dt,
        end_dt=end_dt
    )

    assert result is None
    assert "overdue" in err.lower()

def test_conflict_rejection_when_copies_exhausted():
    """Verify that double booking is rejected when all copies are booked for overlapping times."""
    # High-End AI Workstation Node has exactly 1 physical copy (CRISS-SRV-AI01)
    res = execute_query("SELECT resource_id FROM resources WHERE title LIKE '%AI Workstation Node%';", fetchone=True)
    user1 = execute_query("SELECT user_id FROM users WHERE email = 'student@criss.edu';", fetchone=True)
    user2 = execute_query("SELECT user_id FROM users WHERE email = 'neha@criss.edu';", fetchone=True)

    # Clean existing reservations for this resource in our test window
    start_dt = datetime.now() + timedelta(days=20)
    end_dt = datetime.now() + timedelta(days=22)

    # First booking: takes the only copy
    r1, err1 = ReservationService.create_reservation(
        resource_id=res['resource_id'],
        user_id=user1['user_id'],
        start_dt=start_dt,
        end_dt=end_dt,
        notes="Deep learning epoch training"
    )
    assert err1 is None
    assert r1 is not None

    # Overlapping second booking attempt by user2 during the same window
    overlap_start = start_dt + timedelta(hours=4)
    overlap_end = end_dt + timedelta(hours=4)

    r2, err2 = ReservationService.create_reservation(
        resource_id=res['resource_id'],
        user_id=user2['user_id'],
        start_dt=overlap_start,
        end_dt=overlap_end,
        notes="Conflicting deep learning slot"
    )

    # Must be safely rejected to prevent double-booking!
    assert r2 is None
    assert "reserved or on loan" in err2.lower()

    # Clean up test hold
    ReservationService.cancel_reservation(r1['reservation_id'], user1['user_id'])
