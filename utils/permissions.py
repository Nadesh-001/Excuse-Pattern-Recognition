"""
Permission Utility Functions
=============================
Central permission checking and role-hierarchy validation.

Roles (ascending privilege):
    employee  <  manager  <  secondary_admin  <  main_admin

Two complementary systems:
  has_permission(role, action)                   — fine-grained action-level checks
  role_hierarchy_check(required, actual)         — coarse "at least X" checks
  can_manage_user(actor_role, target_role, ...) — inter-user management checks
"""
import logging
from enum import IntEnum

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Role hierarchy — single definition used by both permission systems.
# ---------------------------------------------------------------------------

class RoleLevel(IntEnum):
    """Numeric hierarchy for role comparison. Higher value = more privilege."""
    employee        = 1
    manager         = 2
    secondary_admin = 3
    admin           = 3   # legacy alias — treated identically to secondary_admin
    main_admin      = 4


def _role_level(role: str) -> int:
    """Return the numeric level for a role string, or 0 for unknown roles."""
    try:
        return RoleLevel[role].value
    except KeyError:
        return 0


# Legacy mapping for backward compatibility with flask_auth.py
ROLE_LEVELS = {r.name: r.value for r in RoleLevel}


def can_manage(actor_role: str, target_role: str) -> bool:
    """
    Return True if actor_role is strictly higher privilege than target_role.

    Notes:
    - main_admin > secondary_admin > manager > employee
    - secondary_admin and legacy 'admin' are at the same level (3)
    - To check inter-user management (including self-guard), use can_manage_user().
    """
    return _role_level(actor_role) > _role_level(target_role)


def can_manage_user(
    actor_role: str,
    target_role: str,
    actor_id: int,
    target_id: int,
) -> bool:
    """
    Return True if actor may manage (delete/edit/deactivate) the target user.

    Rules:
    - No user may manage themselves (self-guard).
    - main_admin may manage any other role (including secondary_admin).
    - secondary_admin may manage manager and employee only.
    - manager/employee may not manage anyone.
    """
    if actor_id == target_id:
        return False  # self-management blocked

    actor_r = actor_role.lower()
    target_r = target_role.lower()

    if actor_r == 'main_admin':
        # main_admin can manage everyone except themselves (already guarded above)
        return True

    if actor_r in ('secondary_admin', 'admin'):
        # secondary_admin can manage manager and employee only
        return target_r in ('manager', 'employee')

    return False


# ---------------------------------------------------------------------------
# Permission table — explicit per-role sets.
# ---------------------------------------------------------------------------

_EMPLOYEE_PERMISSIONS: frozenset = frozenset([
    'view_own_tasks',
    'complete_task',
    'submit_delay',
    'use_chatbot',
    'view_own_analytics',
    'edit_own_profile',
])

_MANAGER_EXTRA_PERMISSIONS: frozenset = frozenset([
    'view_team_tasks',
    'create_task',
    'assign_task',
    'view_team_analytics',
    'export_reports',
    'view_employee_profiles',
])

_SECONDARY_ADMIN_EXTRA_PERMISSIONS: frozenset = frozenset([
    'users.view',
    'users.create',
    'users.delete',
    'users.activate',
    'users.deactivate',
    'users.change_role',
    'reports.view',
    'reports.generate',
    'logs.view',
    'admin_panel',
])

_MAIN_ADMIN_EXTRA_PERMISSIONS: frozenset = frozenset([
    'admins.create',
    'admins.delete',
    'admins.change_role',
    'settings.view',
    'settings.update',
])

# Derived sets
_ROLE_PERMISSIONS = {
    'employee':        _EMPLOYEE_PERMISSIONS,
    'manager':         _EMPLOYEE_PERMISSIONS | _MANAGER_EXTRA_PERMISSIONS,
    'secondary_admin': (
        _EMPLOYEE_PERMISSIONS
        | _MANAGER_EXTRA_PERMISSIONS
        | _SECONDARY_ADMIN_EXTRA_PERMISSIONS
    ),
    'admin': (            # legacy alias
        _EMPLOYEE_PERMISSIONS
        | _MANAGER_EXTRA_PERMISSIONS
        | _SECONDARY_ADMIN_EXTRA_PERMISSIONS
    ),
    'main_admin': (
        _EMPLOYEE_PERMISSIONS
        | _MANAGER_EXTRA_PERMISSIONS
        | _SECONDARY_ADMIN_EXTRA_PERMISSIONS
        | _MAIN_ADMIN_EXTRA_PERMISSIONS
    ),
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def has_permission(user_role: str, action: str) -> bool:
    """
    Return True if user_role may perform action.
    Unknown roles are denied and logged as a warning.
    """
    allowed = _ROLE_PERMISSIONS.get(user_role)
    if allowed is None:
        logger.warning("has_permission: unknown role %r — denying action %r", user_role, action)
        return False
    return action in allowed


def role_hierarchy_check(required_role: str, user_role: str) -> bool:
    """
    Return True if user_role meets or exceeds required_role in the hierarchy.

    Args:
        required_role: Minimum acceptable role ('employee', 'manager',
                       'secondary_admin', 'main_admin').
        user_role:     The user's actual role.
    """
    user_level     = _role_level(user_role)
    required_level = _role_level(required_role)

    if user_level == 0:
        logger.warning("role_hierarchy_check: unknown user_role %r", user_role)
    if required_level == 0:
        logger.warning("role_hierarchy_check: unknown required_role %r", required_role)

    return user_level >= required_level and user_level > 0


def check_task_ownership(task, user_id: int, user_role: str) -> bool:
    """
    Return True if the user may access task.

    Accepts a pre-fetched task dict rather than a task_id so this function
    has no repository dependency and can be unit tested without a database.
    The caller is responsible for fetching the task and handling the
    not-found case (which is a different concern from authorisation).

    Args:
        task:      Task dict with at least an 'assigned_to' key.
        user_id:   The requesting user's ID.
        user_role: The requesting user's role.

    Raises:
        TypeError: If task is None (caller should check existence first).
    """
    if task is None:
        raise TypeError(
            "check_task_ownership received None for task. "
            "Fetch the task and handle the not-found case before calling this function."
        )

    # main_admin, secondary_admin, and manager have full access
    if role_hierarchy_check('manager', user_role):
        return True

    # Employees may only access tasks assigned to them.
    return task.get('assigned_to') == user_id

