"""
Audit Service - System Audit Logging

Provides functions to:
- Log sensitive actions to activity_logs table
- Retrieve activity logs for admin viewing
- Track user activities
"""

from flask import session
from repository.db import execute_query

def log_action(action: str, details: str = None, target_user_id: int = None):
    """
    Log a sensitive action to the activity_logs table.
    
    Args:
        action: Action type (e.g., 'USER_LOGIN', 'ROLE_CHANGED')
        details: Additional details about the action
        target_user_id: Optional ID of affected user
    """
    try:
        user_id = session.get('user_id')
        if not user_id:
            return
        
        full_details = details or ""
        if target_user_id:
            full_details += f" | Target User ID: {target_user_id}"
        
        execute_query(
            "INSERT INTO activity_logs (user_id, action, details) VALUES (%s, %s, %s)",
            (user_id, action, full_details),
            fetch=False
        )
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"Audit log error: {e}")

def get_audit_logs(limit: int = 100, action_filter: str = None):
    """
    Retrieve activity logs from database.
    """
    try:
        if action_filter:
            query = """
                SELECT a.id, a.created_at as timestamp, u.full_name as user_name, u.email, a.action, a.details
                FROM activity_logs a
                JOIN users u ON u.id = a.user_id
                WHERE a.action LIKE %s
                ORDER BY a.created_at DESC
                LIMIT %s
            """
            return execute_query(query, (f"%{action_filter}%", limit))
        else:
            query = """
                SELECT a.id, a.created_at as timestamp, u.full_name as user_name, u.email, a.action, a.details
                FROM activity_logs a
                JOIN users u ON u.id = a.user_id
                ORDER BY a.created_at DESC
                LIMIT %s
            """
            return execute_query(query, (limit,))
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"Error retrieving audit logs: {e}")
        return []


# Common audit action types
class AuditActions:
    USER_LOGIN               = 'USER_LOGIN'
    USER_LOGOUT              = 'USER_LOGOUT'
    ROLE_CHANGED             = 'USER_ROLE_CHANGED'
    TASK_CREATED             = 'TASK_CREATED'
    TASK_DELETED             = 'TASK_DELETED'
    PROFILE_UPDATED          = 'PROFILE_UPDATED'
    PASSWORD_CHANGED         = 'PASSWORD_CHANGED'
    PERMISSION_DENIED        = 'PERMISSION_DENIED'
    USER_REGISTERED          = 'USER_REGISTERED'
    USER_DEACTIVATED         = 'USER_DEACTIVATED'
    USER_REACTIVATED         = 'USER_REACTIVATED'
    USER_UPDATED             = 'USER_UPDATED'
    SECONDARY_ADMIN_CREATED  = 'SECONDARY_ADMIN_CREATED'
    USER_ROLE_CHANGED        = 'USER_ROLE_CHANGED'

