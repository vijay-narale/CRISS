"""
Notification Service for CRISS.
Manages in-app alerts for reservation confirmations, due dates, overdue notices, and demand fulfillments.
"""

from database.connection import execute_query, execute_statement

class NotificationService:
    @staticmethod
    def get_user_notifications(user_id, limit=20):
        """Fetches recent notifications for a user."""
        return execute_query(
            """SELECT notification_id, title, message, category, is_read, created_at
               FROM notifications
               WHERE user_id = %s
               ORDER BY created_at DESC
               LIMIT %s;""",
            (user_id, limit)
        )

    @staticmethod
    def get_unread_count(user_id):
        """Returns the number of unread notifications for navbar badges."""
        res = execute_query(
            "SELECT COUNT(*) AS unread_count FROM notifications WHERE user_id = %s AND is_read = FALSE;",
            (user_id,),
            fetchone=True
        )
        return res['unread_count'] if res else 0

    @staticmethod
    def mark_as_read(notification_id, user_id):
        """Marks a notification as read."""
        execute_statement(
            "UPDATE notifications SET is_read = TRUE WHERE notification_id = %s AND user_id = %s;",
            (notification_id, user_id)
        )

    @staticmethod
    def mark_all_read(user_id):
        """Marks all notifications as read for a user."""
        execute_statement(
            "UPDATE notifications SET is_read = TRUE WHERE user_id = %s AND is_read = FALSE;",
            (user_id,)
        )

    @staticmethod
    def create_notification(user_id, title, message, category='general'):
        """Inserts a new in-app notification."""
        execute_statement(
            """INSERT INTO notifications (user_id, title, message, category)
               VALUES (%s, %s, %s, %s);""",
            (user_id, title, message, category)
        )
