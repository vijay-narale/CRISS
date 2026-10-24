"""
Database Connection and Transaction Management for CRISS.
Uses mysql.connector connection pooling with parameterized query safety.
"""

import logging
from contextlib import contextmanager
import mysql.connector
from mysql.connector import pooling
from config import Config

logger = logging.getLogger(__name__)

# Initialize connection pool singleton
_pool = None

def get_pool():
    global _pool
    if _pool is None:
        try:
            _pool = pooling.MySQLConnectionPool(
                pool_name="criss_pool",
                pool_size=Config.MYSQL_POOL_SIZE,
                pool_reset_session=True,
                host=Config.MYSQL_HOST,
                port=Config.MYSQL_PORT,
                user=Config.MYSQL_USER,
                password=Config.MYSQL_PASSWORD,
                database=Config.MYSQL_DB
            )
            logger.info("MySQL Connection Pool initialized successfully.")
        except Exception as e:
            logger.error(f"Failed to initialize MySQL Connection Pool: {e}")
            raise
    return _pool

@contextmanager
def get_db_cursor(commit=False, dictionary=True):
    """
    Context manager providing a managed MySQL connection and cursor.
    - Automatic rollback on unhandled exceptions
    - Automatic commit if commit=True and no error
    - Guarantees cursor and connection are closed back to the pool
    """
    pool = get_pool()
    conn = pool.get_connection()
    cursor = conn.cursor(dictionary=dictionary)
    try:
        yield conn, cursor
        if commit:
            conn.commit()
    except Exception as e:
        if conn.is_connected():
            conn.rollback()
        logger.error(f"Database transaction error: {e}")
        raise
    finally:
        try:
            cursor.close()
        except Exception:
            pass
        try:
            conn.close()
        except Exception:
            pass

def execute_query(sql, params=None, fetchone=False, fetchall=True, dictionary=True):
    """Convenience helper for read queries with parameterized input."""
    with get_db_cursor(commit=False, dictionary=dictionary) as (conn, cur):
        cur.execute(sql, params or ())
        if fetchone:
            return cur.fetchone()
        if fetchall:
            return cur.fetchall()
        return None

def execute_statement(sql, params=None, commit=True):
    """Convenience helper for INSERT/UPDATE/DELETE queries."""
    with get_db_cursor(commit=commit, dictionary=True) as (conn, cur):
        cur.execute(sql, params or ())
        last_id = cur.lastrowid
        row_count = cur.rowcount
        return {"lastrowid": last_id, "rowcount": row_count}
