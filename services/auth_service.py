"""
Authentication & Authorization Service.
Handles user registration, login, password verification, and session helpers.
"""

from werkzeug.security import generate_password_hash, check_password_hash
from database.connection import get_db_cursor, execute_query, execute_statement

class AuthService:
    @staticmethod
    def authenticate(email, password):
        """Validates credentials and returns user dict if valid, else None."""
        user = execute_query(
            """SELECT u.user_id, u.email, u.password_hash, u.full_name, u.role, 
                      u.department_id, u.student_faculty_id, u.status, d.name AS department_name
               FROM users u
               LEFT JOIN departments d ON u.department_id = d.department_id
               WHERE u.email = %s;""",
            (email.strip().lower(),),
            fetchone=True
        )
        if not user:
            return None, "Invalid email or password."
        
        if user['status'] != 'active':
            return None, "Your account has been deactivated. Please contact campus administration."

        if not check_password_hash(user['password_hash'], password):
            return None, "Invalid email or password."

        # Do not keep password_hash in session data
        user.pop('password_hash', None)
        return user, None

    @staticmethod
    def register_user(email, password, full_name, role, department_id, student_faculty_id, phone=None):
        """Registers a new user with hashed password."""
        email = email.strip().lower()
        if role not in ('student', 'faculty'):
            # Admin accounts must be created internally or via seed
            role = 'student'

        # Check existing email or institutional ID
        existing = execute_query(
            "SELECT user_id FROM users WHERE email = %s OR student_faculty_id = %s;",
            (email, student_faculty_id.strip()),
            fetchone=True
        )
        if existing:
            return None, "A user with this email or Campus ID already exists."

        pwd_hash = generate_password_hash(password)
        with get_db_cursor(commit=True) as (conn, cur):
            cur.execute(
                """INSERT INTO users 
                   (email, password_hash, full_name, role, department_id, phone, student_faculty_id, status)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, 'active');""",
                (email, pwd_hash, full_name.strip(), role, department_id or None, phone, student_faculty_id.strip())
            )
            user_id = cur.lastrowid
            
            # Welcome notification
            cur.execute(
                """INSERT INTO notifications (user_id, title, message, category)
                   VALUES (%s, %s, %s, 'general');""",
                (user_id, 'Welcome to CRISS!', 
                 'Welcome to the Campus Resource Intelligence & Sharing System. Explore available lab kits, textbooks, laptops, and peer listings.')
            )

        return user_id, None

    @staticmethod
    def get_user_by_id(user_id):
        """Fetches user details by user_id."""
        return execute_query(
            """SELECT u.user_id, u.email, u.full_name, u.role, u.department_id, 
                      u.phone, u.student_faculty_id, u.status, d.name AS department_name, d.code AS department_code
               FROM users u
               LEFT JOIN departments d ON u.department_id = d.department_id
               WHERE u.user_id = %s;""",
            (user_id,),
            fetchone=True
        )
