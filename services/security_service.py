"""
Security Service - Enhanced Audit Logging for RBAC
Provides security event logging for unauthorized access attempts and sensitive operations
"""

from services.activity_service import log_activity
from datetime import datetime


def log_security_event(user_id, action, resource, details=None, severity='INFO'):
    """
    Log security-relevant events for audit trail.
    
    Args:
        user_id: User ID performing the action
        action: Action type (e.g., 'UNAUTHORIZED_ACCESS_ATTEMPT', 'ROLE_CHANGE', 'LOGIN_FAILURE')
        resource: Resource being accessed (e.g., '/admin', 'user_id:123', 'task_id:456')
        details: Optional additional context or message
        severity: Event severity level
            - 'INFO': Normal security events (successful login, etc.)
            - 'WARNING': Suspicious but not critical (unauthorized attempts)
            - 'CRITICAL': Serious security issues (repeated failures, privilege escalation attempts)
            
    Returns:
        None (logs to activity_logs table)
        
    Example Usage:
        # Log unauthorized access attempt
        log_security_event(
            user_id=session['user_id'],
            action='UNAUTHORIZED_ACCESS_ATTEMPT',
            resource='/admin',
            details=f"Role: {session.get('user_role')}",
            severity='WARNING'
        )
        
        # Log role change
        log_security_event(
            user_id=admin_id,
            action='ROLE_CHANGE',
            resource=f'user_id:{target_user_id}',
            details=f"{old_role} → {new_role}",
            severity='INFO'
        )
    """
    # Format log message
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    log_message = f"[{severity}] [{timestamp}] {action} on {resource}"
    
    if details:
        log_message += f" - {details}"
    
    # Log to audit_logs table
    try:
        log_activity(user_id, action, log_message)
    except Exception as e:
        # Fallback logging if database fails
        print(f"SECURITY LOG FAILED: {log_message} | Error: {e}")
    
    # For critical events, could also:
    # - Send email alerts to admins
    # - Trigger security monitoring systems
    # - Lock account after repeated failures
    # - Log to external security information and event management (SIEM) system
    
    if severity == 'CRITICAL':
        # TODO: Implement critical event handling
        # send_admin_alert(action, resource, details)
        pass


def log_login_attempt(email, success, reason=None):
    """
    Log login attempts for security monitoring.
    
    Args:
        email: Email address attempting login
        success: Boolean - was login successful?
        reason: Optional reason for failure (e.g., 'invalid_password', 'account_disabled')
    """
    from repository.users_repo import get_user_by_email
    
    user = get_user_by_email(email)
    user_id = user['id'] if user else None
    
    if success:
        if user_id:
            log_security_event(
                user_id=user_id,
                action='LOGIN_SUCCESS',
                resource='/login',
                details=f"Email: {email}",
                severity='INFO'
            )
    else:
        action = 'LOGIN_FAILURE'
        details = f"Email: {email}"
        if reason:
            details += f" | Reason: {reason}"
        
        # Log even if user doesn't exist (could be brute force attempt)
        log_security_event(
            user_id=user_id if user_id else 0,  # Use 0 for non-existent users
            action=action,
            resource='/login',
            details=details,
            severity='WARNING'
        )


def log_permission_denied(user_id, user_role, resource, required_permission=None):
    """
    Log when a user is denied access to a resource.
    
    Args:
        user_id: User attempting access
        user_role: User's current role
        resource: Resource they attempted to access
        required_permission: What permission was needed (optional)
    """
    details = f"Role: {user_role}"
    if required_permission:
        details += f" | Required: {required_permission}"
    
    log_security_event(
        user_id=user_id,
        action='PERMISSION_DENIED',
        resource=resource,
        details=details,
        severity='WARNING'
    )


def log_role_change(admin_id, target_user_id, old_role, new_role, target_email):
    """
    Log when an admin changes a user's role.
    
    Args:
        admin_id: Admin performing the change
        target_user_id: User whose role is being changed
        old_role: Previous role
        new_role: New role
        target_email: Email of user being modified
    """
    log_security_event(
        user_id=admin_id,
        action='ROLE_CHANGE',
        resource=f'user_id:{target_user_id}',
        details=f"{target_email}: {old_role} → {new_role}",
        severity='INFO'
    )


def check_brute_force_attempts(email, max_attempts=5, window_minutes=15):
    """
    Check if there have been too many failed login attempts.
    
    Args:
        email: Email to check
        max_attempts: Maximum failed attempts allowed
        window_minutes: Time window to check (in minutes)
        
    Returns:
        Boolean - True if account should be locked, False otherwise
        
    TODO: Implement this function with database queries
    """
    # Would query audit_logs for LOGIN_FAILURE events
    # within the time window for this email
    # If count >= max_attempts, return True
    
    # Placeholder implementation
    return False
