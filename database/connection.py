"""
Supabase PostgreSQL Connection Manager
Provides connection pooling and database access for the application.
"""

import psycopg2
import psycopg2.pool
import logging
from psycopg2.extras import RealDictCursor
import os
import sys
import platform
from dotenv import load_dotenv
from contextlib import contextmanager

# Load environment variables
load_dotenv()

# Global connection pool
_connection_pool = None

logger = logging.getLogger(__name__)


class DatabaseConnection:
    """
    Supabase PostgreSQL connection manager using connection pooling.
    Provides context manager support for automatic connection handling.
    """

    @staticmethod
    def initialize_pool(min_conn=2, max_conn=10):
        """
        Initialize the connection pool.
        Should be called once at application startup.

        Args:
            min_conn: Minimum number of connections to maintain
            max_conn: Maximum number of connections allowed
        """
        global _connection_pool

        try:
            db_host = os.getenv("DB_HOST")
            db_port = int(os.getenv("DB_PORT", "5432"))
            logger.info("Connecting to Supabase host=%s port=%d ...", db_host, db_port)

            _connection_pool = psycopg2.pool.ThreadedConnectionPool(
                minconn=min_conn,
                maxconn=max_conn,
                host=db_host,
                port=db_port,
                user=os.getenv("DB_USER"),
                password=os.getenv("DB_PASSWORD"),
                database=os.getenv("DB_NAME"),
                sslmode='require',
                connect_timeout=10,
                keepalives=1,
                keepalives_idle=30,
                keepalives_interval=10,
                keepalives_count=5,
                options='-c statement_timeout=30000'
            )
            logger.info("Supabase connection pool initialized successfully")
            logger.info("   Pool size: %d-%d connections", min_conn, max_conn)
            return True
        except Exception as e:
            logger.error("Failed to initialize Supabase pool: %s", e)
            raise

    @staticmethod
    def get_pool():
        """Get the connection pool instance."""
        return _connection_pool

    @staticmethod
    def close_pool():
        """Close all connections in the pool."""
        global _connection_pool
        if _connection_pool:
            _connection_pool.closeall()
            logger.info("Supabase connection pool closed")


def get_conn():
    """
    Get a database connection from the pool.
    Validates connection before returning.
    Uses an iterative retry loop (max 3 attempts) to handle transient failures.
    """
    import time

    max_retries = 2
    retry_count = 0

    while retry_count <= max_retries:
        _connection_pool = DatabaseConnection.get_pool()
        if _connection_pool is None:
            try:
                DatabaseConnection.initialize_pool()
                _connection_pool = DatabaseConnection.get_pool()
            except Exception as init_err:
                logger.error("Pool init attempt %d failed: %s", retry_count, init_err)
                retry_count += 1
                time.sleep(0.5)
                continue

        try:
            conn = _connection_pool.getconn()
            if conn:
                try:
                    with conn.cursor() as tmp_cur:
                        tmp_cur.execute("SELECT 1")
                    conn.cursor_factory = RealDictCursor
                    return conn
                except Exception as check_err:
                    logger.warning("Connection validation failed (attempt %d): %s", retry_count, check_err)
                    _connection_pool.putconn(conn, close=True)
                    retry_count += 1
                    continue

            retry_count += 1
        except Exception as e:
            logger.error("Error acquiring connection (attempt %d): %s", retry_count, e)
            retry_count += 1
            if "pool" in str(e).lower():
                try:
                    DatabaseConnection.initialize_pool()
                except Exception:
                    pass
            time.sleep(0.5)

    raise ConnectionError("Could not acquire database connection after %d retries." % max_retries)


def release_conn(conn, close=False):
    """
    Return a connection back to the pool.

    Args:
        conn: Database connection to release
        close: If True, close the connection (remove from pool)
    """
    if _connection_pool and conn:
        try:
            _connection_pool.putconn(conn, close=close)
        except Exception as e:
            logger.warning("Error releasing connection: %s", e)


@contextmanager
def get_db_connection():
    """
    Context manager for automatic connection handling.
    """
    conn = get_conn()
    close_conn = False
    try:
        yield conn
    except psycopg2.InterfaceError:
        close_conn = True
        raise
    except Exception:
        raise
    finally:
        release_conn(conn, close=close_conn)


@contextmanager
def get_db_cursor(cursor_factory=RealDictCursor):
    """
    Context manager for automatic cursor and connection handling.
    Returns dictionary-based results by default.
    """
    conn = get_conn()
    cursor = None
    close_conn = False
    try:
        cursor = conn.cursor(cursor_factory=cursor_factory)
        yield cursor
        conn.commit()
    except Exception as e:
        try:
            if not conn.closed:
                conn.rollback()
        except Exception as rollback_err:
            print(f"⚠️  Rollback failed: {rollback_err}")

        if isinstance(e, (psycopg2.InterfaceError, psycopg2.OperationalError)):
            close_conn = True

        raise
    finally:
        if cursor:
            try:
                cursor.close()
            except Exception:
                pass

        if conn.closed:
            close_conn = True

        release_conn(conn, close=close_conn)


def execute_query(query, params=None, fetch=True, cursor_factory=RealDictCursor):
    """
    Execute a query with automatic connection management.

    Args:
        query: SQL query string (use %s for parameters)
        params: Query parameters (tuple or dict)
        fetch: If True, returns results. If False, returns affected row count.
        cursor_factory: Cursor type (RealDictCursor for dicts, None for tuples)

    Returns:
        List of results if fetch=True, row count if fetch=False

    Example:
        users = execute_query("SELECT * FROM users WHERE role = %s", ('admin',))
        rows  = execute_query(
            "INSERT INTO users (full_name, email, password_hash, role) VALUES (%s, %s, %s, %s)",
            ('John', 'john@example.com', 'hashed_password', 'employee'),
            fetch=False
        )
    """
    with get_db_cursor(cursor_factory=cursor_factory) as cursor:
        cursor.execute(query, params or ())

        if fetch:
            return cursor.fetchall()
        else:
            return cursor.rowcount


def execute_many(query, params_list):
    """
    Execute the same query with multiple parameter sets (bulk insert).

    Args:
        query: SQL query string
        params_list: List of parameter tuples

    Returns:
        Number of rows affected
    """
    with get_db_cursor() as cursor:
        cursor.executemany(query, params_list)
        return cursor.rowcount


_DIAG_CACHE = None
_DIAG_CACHE_EXPIRY = 0

def test_connection():
    """
    Test Supabase database connection and display system info.
    Used for diagnostics and health checks.

    Returns:
        dict: Connection test results
    """
    global _DIAG_CACHE, _DIAG_CACHE_EXPIRY
    import time
    now = time.time()
    if _DIAG_CACHE is not None and now < _DIAG_CACHE_EXPIRY:
        return _DIAG_CACHE

    try:
        with get_db_cursor() as cursor:
            cursor.execute("SELECT 1 as test")
            cursor.fetchone()

            cursor.execute("SELECT version()")
            version = cursor.fetchone()

            cursor.execute("SELECT current_database()")
            db_name = cursor.fetchone()

            cursor.execute("""
                SELECT count(*) as connections
                FROM pg_stat_activity
                WHERE datname = current_database()
            """)
            connections = cursor.fetchone()

            cursor.execute("""
                SELECT count(*) as table_count
                FROM information_schema.tables
                WHERE table_schema = 'public'
                AND table_type = 'BASE TABLE'
            """)
            table_count = cursor.fetchone()

            res = {
                'database': {
                    'status': True,
                    'message': f"Supabase PostgreSQL connected. Database: {db_name['current_database']}",
                    'version': version['version'],
                    'active_connections': connections['connections'],
                    'tables': table_count['table_count']
                },
                'system': {
                    'Python Version': sys.version,
                    'OS': f"{platform.system()} {platform.release()}"
                }
            }
            _DIAG_CACHE = res
            _DIAG_CACHE_EXPIRY = now + 60
            return res
    except Exception as e:
        return {
            'database': {
                'status': False,
                'message': f"Supabase Connection Error: {str(e)}"
            },
            'system': {
                'Python Version': sys.version,
                'OS': f"{platform.system()} {platform.release()}"
            }
        }



# Alias for backward compatibility
DatabaseConnection.test_connection = test_connection
