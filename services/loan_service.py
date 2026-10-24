"""
Loan & Circulation Service for CRISS.
Coordinates physical checkouts, due dates, returns, overdue monitoring,
maintenance transitions, and leverages MySQL triggers for inventory state synchronization.
"""

from datetime import datetime, timedelta
from database.connection import get_db_cursor, execute_query
from config import Config

class LoanService:
    @staticmethod
    def checkout_resource(barcode, borrower_id, issuer_id=None, reservation_id=None, custom_days=None):
        """
        Processes physical resource checkout.
        Trigger 'trg_after_loan_insert_update_copy' will automatically set copy status to 'on_loan'.
        """
        barcode = barcode.strip()
        with get_db_cursor(commit=True) as (conn, cur):
            # 1. Check if borrower has overdue items
            cur.execute(
                """SELECT COUNT(*) AS overdue_count 
                   FROM loans 
                   WHERE borrower_id = %s AND (status = 'overdue' OR (status = 'active' AND due_date < NOW()));""",
                (borrower_id,)
            )
            if cur.fetchone()['overdue_count'] > 0:
                return None, "Borrower has unresolved overdue loans. Checkout blocked until items are returned."

            # 2. Check active loan limit
            cur.execute(
                "SELECT COUNT(*) AS active_count FROM loans WHERE borrower_id = %s AND status = 'active';",
                (borrower_id,)
            )
            if cur.fetchone()['active_count'] >= Config.MAX_SIMULTANEOUS_LOANS:
                return None, f"Borrower has reached the maximum limit of {Config.MAX_SIMULTANEOUS_LOANS} simultaneous active loans."

            # 3. Fetch copy and category borrow duration
            cur.execute(
                """SELECT rc.copy_id, rc.barcode, rc.status, rc.condition_grade,
                          r.resource_id, r.title, c.max_borrow_days
                   FROM resource_copies rc
                   INNER JOIN resources r ON rc.resource_id = r.resource_id
                   INNER JOIN categories c ON r.category_id = c.category_id
                   WHERE rc.barcode = %s
                   FOR UPDATE;""",
                (barcode,)
            )
            copy = cur.fetchone()
            if not copy:
                return None, f"No inventory copy found with barcode '{barcode}'."

            if copy['status'] not in ('available', 'reserved'):
                return None, f"Copy #{barcode} is currently '{copy['status']}' and cannot be issued."

            # 4. If reserved, verify reservation ownership
            if reservation_id:
                cur.execute(
                    """SELECT reservation_id, user_id, status 
                       FROM reservations 
                       WHERE reservation_id = %s FOR UPDATE;""",
                    (reservation_id,)
                )
                resv = cur.fetchone()
                if not resv:
                    return None, "Referenced reservation not found."
                if resv['user_id'] != borrower_id:
                    return None, "Reservation belongs to a different student."
                if resv['status'] not in ('confirmed', 'pending_approval'):
                    return None, f"Reservation is already '{resv['status']}'."

            # Calculate loan period
            days = custom_days if custom_days else copy['max_borrow_days']
            now = datetime.now()
            due_date = now + timedelta(days=days)

            # 5. Insert loan record
            cur.execute(
                """INSERT INTO loans 
                   (reservation_id, copy_id, borrower_id, issuer_id, checkout_date, due_date, status, checkout_condition)
                   VALUES (%s, %s, %s, %s, %s, %s, 'active', %s);""",
                (reservation_id, copy['copy_id'], borrower_id, issuer_id, now, due_date, copy['condition_grade'])
            )
            loan_id = cur.lastrowid

            # 6. Update reservation if linked
            if reservation_id:
                cur.execute(
                    "UPDATE reservations SET status = 'fulfilled' WHERE reservation_id = %s;",
                    (reservation_id,)
                )

            # 7. In-app notification to borrower
            cur.execute(
                """INSERT INTO notifications (user_id, title, message, category)
                   VALUES (%s, %s, %s, 'general');""",
                (borrower_id, "Resource Checked Out",
                 f"You checked out '{copy['title']}' (#{copy['barcode']}). Due on {due_date.strftime('%b %d, %Y %I:%M %p')}.")
            )

            return {
                "loan_id": loan_id,
                "barcode": copy['barcode'],
                "title": copy['title'],
                "due_date": due_date
            }, None

    @staticmethod
    def return_resource(loan_id, return_condition='Good', notes="", admin_user_id=None):
        """
        Processes resource return.
        Trigger 'trg_after_loan_return_update_copy' will automatically mark copy as 'available'.
        If return_condition is 'Needs Maintenance', copy is transferred to maintenance workflow.
        """
        with get_db_cursor(commit=True) as (conn, cur):
            cur.execute(
                """SELECT l.loan_id, l.copy_id, l.borrower_id, l.due_date, l.status,
                          rc.barcode, r.title
                   FROM loans l
                   INNER JOIN resource_copies rc ON l.copy_id = rc.copy_id
                   INNER JOIN resources r ON rc.resource_id = r.resource_id
                   WHERE l.loan_id = %s
                   FOR UPDATE;""",
                (loan_id,)
            )
            loan = cur.fetchone()
            if not loan:
                return False, "Loan record not found."

            if loan['status'] == 'returned':
                return False, "Item has already been marked returned."

            now = datetime.now()
            days_overdue = max(0, (now - loan['due_date']).days)
            fine_amount = days_overdue * Config.MAX_OVERDUE_FINE_PER_DAY

            # 1. Update loan record to 'returned'
            cur.execute(
                """UPDATE loans 
                   SET status = 'returned', return_date = %s, return_condition = %s, 
                       notes = CONCAT(IFNULL(notes, ''), ' ', %s)
                   WHERE loan_id = %s;""",
                (now, return_condition, notes, loan_id)
            )

            # 2. Check if damage / maintenance is required
            needs_maint = return_condition in ('Needs Maintenance', 'Fair') and 'damage' in notes.lower()
            if return_condition == 'Needs Maintenance' or needs_maint:
                cur.execute(
                    "UPDATE resource_copies SET status = 'maintenance', condition_grade = 'Needs Maintenance' WHERE copy_id = %s;",
                    (loan['copy_id'],)
                )
                cur.execute(
                    """INSERT INTO maintenance_records (copy_id, reported_by, issue_description, status)
                       VALUES (%s, %s, %s, 'reported');""",
                    (loan['copy_id'], admin_user_id or loan['borrower_id'], 
                     f"Returned in damaged/maintenance condition: {notes or 'Wear and tear detected at return.'}")
                )

            # 3. Notification to borrower
            overdue_msg = f" (Late return by {days_overdue} days, assessed fine: ${fine_amount:.2f})" if days_overdue > 0 else ""
            cur.execute(
                """INSERT INTO notifications (user_id, title, message, category)
                   VALUES (%s, %s, %s, 'general');""",
                (loan['borrower_id'], "Return Received",
                 f"Return confirmed for '{loan['title']}' (#{loan['barcode']}){overdue_msg}. Thank you for using CRISS.")
            )

            return True, f"Resource returned successfully.{overdue_msg}"

    @staticmethod
    def scan_and_update_overdue():
        """Scans all active loans and flags overdue status with automated notification."""
        with get_db_cursor(commit=True) as (conn, cur):
            cur.execute(
                """SELECT l.loan_id, l.borrower_id, l.due_date, r.title, rc.barcode
                   FROM loans l
                   INNER JOIN resource_copies rc ON l.copy_id = rc.copy_id
                   INNER JOIN resources r ON rc.resource_id = r.resource_id
                   WHERE l.status = 'active' AND l.due_date < NOW();"""
            )
            overdue_loans = cur.fetchall()

            count = 0
            for row in overdue_loans:
                cur.execute("UPDATE loans SET status = 'overdue' WHERE loan_id = %s;", (row['loan_id'],))
                # Send overdue alert
                cur.execute(
                    """INSERT INTO notifications (user_id, title, message, category)
                       VALUES (%s, %s, %s, 'overdue');""",
                    (row['borrower_id'], "URGENT: Overdue Resource Notice",
                     f"'{row['title']}' (#{row['barcode']}) was due on {row['due_date'].strftime('%b %d, %Y')}. Please return it immediately to avoid administrative holds.")
                )
                count += 1
            return count

    @staticmethod
    def get_user_loans(user_id):
        """Fetches active, overdue, and returned loan history for a user."""
        return execute_query(
            """SELECT 
                   l.loan_id,
                   r.title AS resource_title,
                   c.name AS category_name,
                   rc.barcode,
                   l.checkout_date,
                   l.due_date,
                   l.return_date,
                   l.status,
                   l.checkout_condition,
                   l.return_condition,
                   DATEDIFF(NOW(), l.due_date) AS days_overdue
               FROM loans l
               INNER JOIN resource_copies rc ON l.copy_id = rc.copy_id
               INNER JOIN resources r ON rc.resource_id = r.resource_id
               INNER JOIN categories c ON r.category_id = c.category_id
               WHERE l.borrower_id = %s
               ORDER BY l.checkout_date DESC;""",
            (user_id,)
        )
