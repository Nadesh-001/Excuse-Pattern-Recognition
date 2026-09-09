"""
Permission Service - RBAC Permission Management

Provides functions to:
- Load permissions for a role from hardcoded mapping
- Check if current user has a permission
- Guard/protect pages and features
"""

from flask import session, abort, flash

# Permission Constants (for easy reference)
class Permissions:
    VIEW_DASHBOARD    = 'VIEW_DASHBOARD'
    VIEW_TASKS        = 'VIEW_TASKS'
    CREATE_TASK       = 'CREATE_TASK'
    EDIT_TASK         = 'EDIT_TASK'
    DELETE_TASK       = 'DELETE_TASK'
    VIEW_ANALYTICS    = 'VIEW_ANALYTICS'
    MANAGE_EMPLOYEES  = 'MANAGE_EMPLOYEES'
    ADMIN_PANEL       = 'ADMIN_PANEL'
    VIEW_AUDIT_LOGS   = 'VIEW_AUDIT_LOGS'
    EDIT_PROFILE      = 'EDIT_PROFILE'
    MANAGE_ROLES      = 'MANAGE_ROLES'
    USE_CHATBOT       = 'USE_CHATBOT'
    MANAGE_ADMINS     = 'MANAGE_ADMINS'   # main_admin only


# Base permission sets
_EMPLOYEE_PERMS = {
    Permissions.VIEW_DASHBOARD, Permissions.VIEW_TASKS,
    Permissions.VIEW_ANALYTICS, Permissions.EDIT_PROFILE,
    Permissions.USE_CHATBOT,
}
_ADMIN_PERMS = {
    Permissions.VIEW_DASHBOARD, Permissions.VIEW_TASKS, Permissions.CREATE_TASK,
    Permissions.EDIT_TASK, Permissions.DELETE_TASK, Permissions.VIEW_ANALYTICS,
    Permissions.MANAGE_EMPLOYEES, Permissions.ADMIN_PANEL, Permissions.VIEW_AUDIT_LOGS,
    Permissions.EDIT_PROFILE, Permissions.MANAGE_ROLES, Permissions.USE_CHATBOT,
}

# Hardcoded permission mapping
ROLE_PERMISSIONS = {
    'main_admin': _ADMIN_PERMS | {Permissions.MANAGE_ADMINS},
    'secondary_admin': _ADMIN_PERMS,
    'admin':     _ADMIN_PERMS,       # legacy alias
    'manager': {
        Permissions.VIEW_DASHBOARD, Permissions.VIEW_TASKS, Permissions.CREATE_TASK,
        Permissions.EDIT_TASK, Permissions.DELETE_TASK, Permissions.VIEW_ANALYTICS,
        Permissions.MANAGE_EMPLOYEES, Permissions.EDIT_PROFILE, Permissions.USE_CHATBOT,
    },
    'employee': _EMPLOYEE_PERMS,
}


def get_permissions_for_role(role: str) -> set:
    """
    Get all permission codes for a given role (Local Mapping).
    Falls back to employee permissions for unknown roles.
    """
    return ROLE_PERMISSIONS.get(role.lower(), _EMPLOYEE_PERMS)


def load_user_permissions():
    """
    Load permissions for current user and store in session.
    """
    user_role = session.get('user_role', 'employee')
    session['permissions'] = list(get_permissions_for_role(user_role))


def has_permission(permission_code: str) -> bool:
    """
    Check if current user has a specific permission.

    Args:
        permission_code: Permission code to check (e.g., 'VIEW_ANALYTICS')

    Returns:
        True if user has permission, False otherwise
    """
    if 'permissions' not in session:
        load_user_permissions()

    return permission_code in session.get('permissions', [])


def require_permission(permission_code: str, error_message: str = None):
    """
    Guard function - stops page execution if user lacks permission.

    Args:
        permission_code: Required permission
        error_message: Optional custom error message
    """
    if not has_permission(permission_code):
        if error_message is None:
            error_message = f"⛔ Access Denied: You need '{permission_code}' permission to access this page."

        flash(error_message, "error")
        abort(403)

