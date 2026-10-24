"""
Test Suite: Authentication, Password Hashing, and Role Authorization.
"""

import pytest
from werkzeug.security import check_password_hash
from services.auth_service import AuthService
from database.connection import execute_query, execute_statement

def test_admin_authentication():
    """Verify admin login with valid seed credentials."""
    user, err = AuthService.authenticate('admin@criss.edu', 'AdminPassword@123')
    assert err is None
    assert user is not None
    assert user['role'] == 'admin'
    assert user['email'] == 'admin@criss.edu'

def test_student_authentication():
    """Verify student login with valid seed credentials."""
    user, err = AuthService.authenticate('student@criss.edu', 'StudentPassword@123')
    assert err is None
    assert user is not None
    assert user['role'] == 'student'

def test_invalid_password_rejection():
    """Verify that wrong passwords are safely rejected without leaking account info."""
    user, err = AuthService.authenticate('admin@criss.edu', 'WrongPasswordXYZ')
    assert user is None
    assert "Invalid email or password" in err

def test_nonexistent_user():
    """Verify that non-existent users are rejected safely."""
    user, err = AuthService.authenticate('ghost@criss.edu', 'SomePassword123')
    assert user is None
    assert "Invalid email or password" in err

def test_user_registration_and_hash():
    """Verify new user registration with properly salted and hashed password."""
    test_email = "test.newstudent@criss.edu"
    test_id = "STU-TEST-999"

    # Clean up if exists from previous test run
    execute_statement("DELETE FROM users WHERE email = %s OR student_faculty_id = %s;", (test_email, test_id))

    user_id, err = AuthService.register_user(
        email=test_email,
        password="MySecretPassword@2026",
        full_name="Test Student User",
        role="student",
        department_id=1,
        student_faculty_id=test_id,
        phone="+1-555-0999"
    )

    assert err is None
    assert user_id is not None

    # Verify directly from DB that password was hashed
    db_user = execute_query(
        "SELECT password_hash, role FROM users WHERE user_id = %s;",
        (user_id,),
        fetchone=True
    )
    assert db_user is not None
    assert db_user['password_hash'] != "MySecretPassword@2026"
    assert check_password_hash(db_user['password_hash'], "MySecretPassword@2026")

    # Verify authentication succeeds with the registered credentials
    auth_user, auth_err = AuthService.authenticate(test_email, "MySecretPassword@2026")
    assert auth_err is None
    assert auth_user['user_id'] == user_id

    # Clean up
    execute_statement("DELETE FROM users WHERE user_id = %s;", (user_id,))
