from .db import execute_query
import logging

logger = logging.getLogger(__name__)

def create_log(user_id, action, details):
    """Create an audit log entry."""
    try:
        execute_query(
            "INSERT INTO activity_logs (user_id, action, details) VALUES (%s, %s, %s)",
            (user_id, action, details),
            fetch=False
        )
    except Exception as e:
        # Don't crash the main flow if logging fails
        logger.error("Failed to create audit log: %s", e)

def get_recent_logs(limit=50):
    """Retrieve recent activity logs with user info."""
    query = """
        SELECT l.*, l.created_at as timestamp, u.full_name as user_name, u.email as user_email
        FROM activity_logs l
        LEFT JOIN users u ON l.user_id = u.id
        ORDER BY l.created_at DESC
        LIMIT %s
    """
    return execute_query(query, (limit,))
