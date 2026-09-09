from functools import wraps
from flask import session, redirect, url_for, flash, request
from repository.users_repo import update_last_active

# ---------------------------------------------------------------------------
# Role hierarchy — single source of truth lives in permissions.py
# ---------------------------------------------------------------------------

from utils.permissions import ROLE_LEVELS, can_manage

_MANAGER_ROLES    = {'main_admin', 'secondary_admin', 'admin', 'manager'}
_ADMIN_ROLES      = {'main_admin', 'secondary_admin', 'admin'}
_MAIN_ADMIN_ROLES = {'main_admin'}


def role_rank(role: str) -> int:
    """Return numeric rank for a role string. Unknown roles get 0."""
    return ROLE_LEVELS.get(role, 0)


def can_manage_user(actor_role: str, target_role: str) -> bool:
    """Re-export for backward compatibility."""
    return can_manage(actor_role, target_role)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _redirect_to_login(message: str = "Please log in to access this page."):
    """
    Redirect to the login page, preserving the originally requested URL.

    The login view should read `request.args.get('next')` and redirect
    there after successful authentication (validate it is a relative path
    before using it to prevent open-redirect attacks).
    """
    flash(message, "warning")
    return redirect(url_for('auth.login', next=request.url))


def _check_authenticated() -> bool:
    return 'user_id' in session


def _check_role(allowed_roles: set) -> bool:
    """
    Check the session role against an allowed set.

    Note: this trusts the session value set at login. If a user's role is
    changed in the database after they authenticate, the change won't take
    effect until their next login. For stronger guarantees, replace this
    with a DB lookup on every request (at a per-request latency cost).
    """
    return session.get('user_role', '').lower() in allowed_roles


# ---------------------------------------------------------------------------
# Public decorators
# ---------------------------------------------------------------------------


def auth_required(f):
    """Allow any authenticated user."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if not _check_authenticated():
            return _redirect_to_login()
        
        # Track activity
        try:
            update_last_active(session['user_id'])
        except Exception:
            pass # Don't block request on logging failure
            
        return f(*args, **kwargs)
    return decorated


def admin_required(f):
    """Allow admins only. Redirects unauthenticated users to login."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if not _check_authenticated():
            return _redirect_to_login()
        if not _check_role(_ADMIN_ROLES):
            flash("Admin access required.", "error")
            return redirect(url_for('dashboard.dashboard'))
        return f(*args, **kwargs)
    return decorated


def manager_required(f):
    """Allow managers and admins. Redirects unauthenticated users to login."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if not _check_authenticated():
            return _redirect_to_login()
        if not _check_role(_MANAGER_ROLES):
            flash("Manager access required.", "error")
            return redirect(url_for('dashboard.dashboard'))
        return f(*args, **kwargs)
    return decorated


def main_admin_required(f):
    """Allow main_admin only. Use for operations exclusive to the primary administrator."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if not _check_authenticated():
            return _redirect_to_login()
        if not _check_role(_MAIN_ADMIN_ROLES):
            flash("Main Admin access required.", "error")
            return redirect(url_for('dashboard.dashboard'))
        return f(*args, **kwargs)
    return decorated
