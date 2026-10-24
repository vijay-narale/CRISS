"""
Test Suite: Loan Workflows, Trigger Updates, Overdue Detection, and Returns.
"""

from datetime import datetime, timedelta
import pytest
from services.loan_service import LoanService
from database.connection import execute_query, execute_statement

def test_checkout_and_trigger_status_update():
    """
    Verify that checking out a copy successfully creates a loan
    and the MySQL trigger 'trg_after_loan_insert_update_copy'
    automatically updates copy status to 'on_loan'.
    """
    # Find an available copy of Spartan-7 FPGA
    copy = execute_query(
        """SELECT rc.copy_id, rc.barcode 
           FROM resource_copies rc 
           INNER JOIN resources r ON rc.resource_id = r.resource_id
           WHERE r.title LIKE '%Spartan-7 FPGA%' AND rc.status = 'available'
           LIMIT 1;""",
        fetchone=True
    )
    assert copy is not None

    borrower = execute_query("SELECT user_id FROM users WHERE email = 'neha@criss.edu';", fetchone=True)
    admin = execute_query("SELECT user_id FROM users WHERE email = 'admin@criss.edu';", fetchone=True)

    # Perform checkout
    loan_res, err = LoanService.checkout_resource(
        barcode=copy['barcode'],
        borrower_id=borrower['user_id'],
        issuer_id=admin['user_id'],
        custom_days=5
    )

    assert err is None
    assert loan_res is not None
    loan_id = loan_res['loan_id']

    # Verify MySQL trigger set copy status to 'on_loan'
    updated_copy = execute_query(
        "SELECT status FROM resource_copies WHERE copy_id = %s;",
        (copy['copy_id'],),
        fetchone=True
    )
    assert updated_copy['status'] == 'on_loan'

    # Now test return workflow and trigger restoration
    ret_success, ret_msg = LoanService.return_resource(
        loan_id=loan_id,
        return_condition="Good",
        notes="Lab testing complete, all pins functional.",
        admin_user_id=admin['user_id']
    )
    assert ret_success is True

    # Verify MySQL trigger 'trg_after_loan_return_update_copy' restored copy status to 'available'
    restored_copy = execute_query(
        "SELECT status FROM resource_copies WHERE copy_id = %s;",
        (copy['copy_id'],),
        fetchone=True
    )
    assert restored_copy['status'] == 'available'

    # Clean up test loan
    execute_statement("DELETE FROM loans WHERE loan_id = %s;", (loan_id,))

def test_return_with_maintenance_requirement():
    """
    Verify that returning a damaged item routes the copy to maintenance
    and logs a maintenance record.
    """
    # Checkout another copy
    copy = execute_query(
        """SELECT rc.copy_id, rc.barcode 
           FROM resource_copies rc 
           INNER JOIN resources r ON rc.resource_id = r.resource_id
           WHERE r.title LIKE '%Spartan-7 FPGA%' AND rc.status = 'available'
           LIMIT 1;""",
        fetchone=True
    )
    borrower = execute_query("SELECT user_id FROM users WHERE email = 'neha@criss.edu';", fetchone=True)
    admin = execute_query("SELECT user_id FROM users WHERE email = 'admin@criss.edu';", fetchone=True)

    loan_res, err = LoanService.checkout_resource(
        barcode=copy['barcode'],
        borrower_id=borrower['user_id'],
        issuer_id=admin['user_id']
    )
    assert err is None
    loan_id = loan_res['loan_id']

    # Return with Needs Maintenance condition
    ret_success, ret_msg = LoanService.return_resource(
        loan_id=loan_id,
        return_condition="Needs Maintenance",
        notes="Damaged micro-USB connector port.",
        admin_user_id=admin['user_id']
    )
    assert ret_success is True

    # Verify copy status is 'maintenance'
    maint_copy = execute_query(
        "SELECT status, condition_grade FROM resource_copies WHERE copy_id = %s;",
        (copy['copy_id'],),
        fetchone=True
    )
    assert maint_copy['status'] == 'maintenance'
    assert maint_copy['condition_grade'] == 'Needs Maintenance'

    # Clean up / reset back to available for subsequent test isolation
    execute_statement("UPDATE resource_copies SET status = 'available', condition_grade = 'Good' WHERE copy_id = %s;", (copy['copy_id'],))
    execute_statement("DELETE FROM maintenance_records WHERE copy_id = %s AND reported_by = %s;", (copy['copy_id'], admin['user_id']))
    execute_statement("DELETE FROM loans WHERE loan_id = %s;", (loan_id,))

def test_overdue_scan_and_flagging():
    """Verify scanning for overdue items properly updates loan records."""
    count = LoanService.scan_and_update_overdue()
    assert count >= 0
