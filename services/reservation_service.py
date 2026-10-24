"""
Reservation Service for CRISS.
Implements ACID-compliant reservation booking with row locking (SELECT ... FOR UPDATE),
conflict detection over time windows, double-booking prevention, and audit logging.
"""

from datetime import datetime
from database.connection import get_db_cursor, execute_query

class ReservationService:
    @staticmethod
    def create_reservation(resource_id, user_id, start_dt, end_dt, notes=""):
        """
        Creates a time-bounded reservation using transactional row locking.
        Prevents double-booking and concurrent conflicting allocations.
        """
        if start_dt >= end_dt:
            return None, "Reservation end time must be after start time."
        
        now = datetime.now()
        if end_dt <= now:
            return None, "Reservation time window cannot be in the past."

        with get_db_cursor(commit=True) as (conn, cur):
            # 1. Check if user has active overdue loans
            cur.execute(
                """SELECT COUNT(*) AS overdue_count 
                   FROM loans 
                   WHERE borrower_id = %s AND (status = 'overdue' OR (status = 'active' AND due_date < NOW()));""",
                (user_id,)
            )
            res_user = cur.fetchone()
            if res_user and res_user['overdue_count'] > 0:
                return None, "You currently have overdue items. Please return them before making new reservations."

            # 2. Retrieve resource metadata & lock the resource row
            cur.execute(
                """SELECT resource_id, title, category_id, requires_approval, owner_type
                   FROM resources
                   WHERE resource_id = %s
                   FOR UPDATE;""",
                (resource_id,)
            )
            resource = cur.fetchone()
            if not resource:
                return None, "Resource not found."

            # Determine reservation status
            # If requires approval, status is 'pending_approval'; otherwise 'confirmed'
            # (Admins or faculty auto-confirm)
            cur.execute("SELECT role FROM users WHERE user_id = %s;", (user_id,))
            user_role = cur.fetchone()['role']
            
            if resource['requires_approval'] and user_role == 'student':
                initial_status = 'pending_approval'
            else:
                initial_status = 'confirmed'

            # 3. Find an available physical copy not locked by conflicting reservations
            # Overlap condition: NOT (res.end_datetime <= start_dt OR res.start_datetime >= end_dt)
            cur.execute(
                """SELECT rc.copy_id, rc.barcode
                   FROM resource_copies rc
                   WHERE rc.resource_id = %s
                     AND rc.status IN ('available', 'reserved')
                     AND rc.copy_id NOT IN (
                         SELECT res.copy_id 
                         FROM reservations res
                         WHERE res.resource_id = %s
                           AND res.copy_id IS NOT NULL
                           AND res.status IN ('confirmed', 'pending_approval')
                           AND NOT (res.end_datetime <= %s OR res.start_datetime >= %s)
                     )
                   ORDER BY rc.copy_id ASC
                   LIMIT 1
                   FOR UPDATE;""",
                (resource_id, resource_id, start_dt, end_dt)
            )
            candidate = cur.fetchone()

            if not candidate:
                # Inventory is fully booked or unavailable for this window
                return None, "All copies of this resource are reserved or on loan during the requested time slot."

            copy_id = candidate['copy_id']

            # 4. Insert reservation record
            cur.execute(
                """INSERT INTO reservations 
                   (resource_id, copy_id, user_id, start_datetime, end_datetime, status, notes)
                   VALUES (%s, %s, %s, %s, %s, %s, %s);""",
                (resource_id, copy_id, user_id, start_dt, end_dt, initial_status, notes)
            )
            reservation_id = cur.lastrowid

            # 5. If starts immediately and confirmed, update copy status
            if start_dt <= now and initial_status == 'confirmed':
                cur.execute(
                    "UPDATE resource_copies SET status = 'reserved' WHERE copy_id = %s;",
                    (copy_id,)
                )

            # 6. Audit logging
            cur.execute(
                """INSERT INTO usage_logs (entity_type, entity_id, user_id, action, details)
                   VALUES ('RESERVATION', %s, %s, 'RESERVE', %s);""",
                (reservation_id, user_id, 
                 f"Booked copy #{candidate['barcode']} ({start_dt.strftime('%Y-%m-%d %H:%M')} to {end_dt.strftime('%Y-%m-%d %H:%M')})")
            )

            # 7. In-app notification
            notif_title = "Reservation Confirmed" if initial_status == 'confirmed' else "Reservation Pending Approval"
            notif_msg = (f"Your reservation for '{resource['title']}' (#{candidate['barcode']}) is confirmed."
                         if initial_status == 'confirmed' else
                         f"Your reservation for '{resource['title']}' has been submitted for faculty/admin coordinator review.")
            
            cur.execute(
                """INSERT INTO notifications (user_id, title, message, category)
                   VALUES (%s, %s, %s, %s);""",
                (user_id, notif_title, notif_msg, 'reservation_approved' if initial_status == 'confirmed' else 'general')
            )

            return {
                "reservation_id": reservation_id,
                "status": initial_status,
                "copy_barcode": candidate['barcode'],
                "resource_title": resource['title']
            }, None

    @staticmethod
    def cancel_reservation(reservation_id, user_id, is_admin=False):
        """Cancels a reservation and releases any reserved copy back to available."""
        with get_db_cursor(commit=True) as (conn, cur):
            cur.execute(
                """SELECT r.reservation_id, r.user_id, r.copy_id, r.status, res.title
                   FROM reservations r
                   INNER JOIN resources res ON r.resource_id = res.resource_id
                   WHERE r.reservation_id = %s
                   FOR UPDATE;""",
                (reservation_id,)
            )
            resv = cur.fetchone()
            if not resv:
                return False, "Reservation not found."

            if not is_admin and resv['user_id'] != user_id:
                return False, "Unauthorized: You may only cancel your own reservations."

            if resv['status'] not in ('confirmed', 'pending_approval'):
                return False, f"Cannot cancel reservation with status '{resv['status']}'."

            cur.execute(
                "UPDATE reservations SET status = 'cancelled' WHERE reservation_id = %s;",
                (reservation_id,)
            )

            # Release copy status if it was set to reserved
            if resv['copy_id']:
                cur.execute(
                    """UPDATE resource_copies 
                       SET status = 'available' 
                       WHERE copy_id = %s AND status = 'reserved';""",
                    (resv['copy_id'],)
                )

            # Audit log
            cur.execute(
                """INSERT INTO usage_logs (entity_type, entity_id, user_id, action, details)
                   VALUES ('RESERVATION', %s, %s, 'CANCEL', 'Reservation cancelled.');""",
                (reservation_id, user_id)
            )

            return True, "Reservation cancelled successfully."

    @staticmethod
    def approve_reservation(reservation_id, admin_id, approve=True, notes=""):
        """Approves or rejects a pending reservation."""
        with get_db_cursor(commit=True) as (conn, cur):
            cur.execute(
                """SELECT r.reservation_id, r.user_id, r.resource_id, r.copy_id, r.status, res.title
                   FROM reservations r
                   INNER JOIN resources res ON r.resource_id = res.resource_id
                   WHERE r.reservation_id = %s
                   FOR UPDATE;""",
                (reservation_id,)
            )
            resv = cur.fetchone()
            if not resv:
                return False, "Reservation not found."

            if resv['status'] != 'pending_approval':
                return False, f"Reservation is currently '{resv['status']}', not pending approval."

            new_status = 'confirmed' if approve else 'rejected'
            cur.execute(
                """UPDATE reservations 
                   SET status = %s, approval_admin_id = %s, notes = CONCAT(IFNULL(notes, ''), ' [Admin: ', %s, ']')
                   WHERE reservation_id = %s;""",
                (new_status, admin_id, notes, reservation_id)
            )

            # Notification to user
            title = "Reservation Approved!" if approve else "Reservation Request Declined"
            msg = (f"Your reservation for '{resv['title']}' has been approved by the department coordinator."
                   if approve else
                   f"Your reservation for '{resv['title']}' was declined. Reason: {notes or 'Capacity constraint'}")
            
            cur.execute(
                """INSERT INTO notifications (user_id, title, message, category)
                   VALUES (%s, %s, %s, %s);""",
                (resv['user_id'], title, msg, 'reservation_approved' if approve else 'general')
            )

            return True, f"Reservation has been {new_status}."

    @staticmethod
    def get_user_reservations(user_id):
        """Fetches active and historical reservations for a student."""
        return execute_query(
            """SELECT 
                   r.reservation_id,
                   res.title AS resource_title,
                   c.name AS category_name,
                   rc.barcode,
                   r.start_datetime,
                   r.end_datetime,
                   r.status,
                   r.notes,
                   r.created_at
               FROM reservations r
               INNER JOIN resources res ON r.resource_id = res.resource_id
               INNER JOIN categories c ON res.category_id = c.category_id
               LEFT JOIN resource_copies rc ON r.copy_id = rc.copy_id
               WHERE r.user_id = %s
               ORDER BY r.start_datetime DESC;""",
            (user_id,)
        )
