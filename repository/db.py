"""
Database Connection Module - AWS RDS PostgreSQL
This module provides database connections for the repository layer.
Migrated from Supabase to AWS RDS (direct psycopg2 connection).
"""

from database.connection import (
    get_conn, 
    release_conn, 
    DatabaseConnection,
    get_db_connection,
    get_db_cursor,
    execute_query,
    execute_many,
    test_connection
)

# Re-export all functions
__all__ = [
    'get_conn',
    'release_conn', 
    'DatabaseConnection',
    'get_db_connection',
    'get_db_cursor',
    'execute_query',
    'execute_many',
    'test_connection'
]

# Legacy function for backward compatibility
def get_pool():
    """
    Legacy function - returns the connection pool instance.
    For backward compatibility with MySQL/TiDB code.
    
    Note: With PostgreSQL pooling, you typically don't need direct pool access.
    Use get_conn() and release_conn() instead.
    """
    return DatabaseConnection.get_pool()
