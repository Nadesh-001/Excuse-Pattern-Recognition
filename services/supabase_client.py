"""
AWS RDS Database Client — Stub
Previously: Supabase client for RLS-bypassed operations.
Now: thin wrapper around the standard psycopg2 connection pool.

All calls to get_supabase_client() return None gracefully so that
any legacy callers (upload_service, etc.) don't crash.
"""

import logging
from database.connection import get_db_connection, execute_query

logger = logging.getLogger(__name__)


def get_supabase_client():
    """
    Legacy stub — returns None.
    All database operations now use psycopg2 via database.connection.
    """
    logger.debug("get_supabase_client() called — returning None (Supabase removed)")
    return None


# Expose connection helpers under a familiar namespace for any consumers
# that previously used supabase_client imports.
__all__ = ["get_supabase_client", "get_db_connection", "execute_query"]
