import re
import hashlib

from flask import current_app

from repository.users_repo import (
    get_user_by_email,
    get_user_by_id,
    create_user,
    update_password_hash,
)
from utils.hashing import verify_password, hash_password, pwd_context
from services.activity_service import log_activity
from services.audit_service import log_action, AuditActions


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_EMAIL_RE       = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')
_MIN_PW_LENGTH  = 8
_BASELINE_HASH  = hash_password("__auth_timing_baseline__")  # see authenticate_user


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _log_email_hash(email: str) -> str:
    """One-way truncated hash of an email for safe logging (not reversible)."""
    return hashlib.sha256(email.lower().encode()).hexdigest()[:12]


def _rehash_if_needed(user_id: int, password: str, current_hash: str) -> None:
    """Transparently upgrade the stored hash if the policy has changed."""
    try:
        if pwd_context.needs_update(current_hash):
            current_app.logger.info("Rehashing password for user_id=%s", user_id)
            update_password_hash(user_id, hash_password(password))
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def authenticate_user(email: str, password: str, role: str = None):
    """
    Authenticate a user by email and password.

    Returns the user dict on success, or None on any authentication failure.
    Raises ValueError for structurally invalid inputs.

    Timing note: verify_password is always called (against a baseline hash when
    the user doesn't exist) to prevent user-enumeration via response time.
    """
    if not email or not password:
        raise ValueError("Email and password are required")

    email = email.strip()
    # Do NOT strip the password — leading/trailing spaces are valid characters.

    from repository.db import execute_query
    if role and role.lower() in ('admin', 'manager', 'employee'):
        login_table = f"{role.lower()}_login"
        res = execute_query(f"SELECT user_id, password_hash FROM {login_table} WHERE email = %s", (email.lower(),))
        if res:
            user = get_user_by_id(res[0]['user_id'])
            # Ensure the password hash matches the one from the specialized table
            if user:
                user['password_hash'] = res[0]['password_hash']
        else:
            user = None
    else:
        user = get_user_by_email(email)

    if not user:
        # Run a timing baseline verification to equalise response time.
        verify_password(password, _BASELINE_HASH)
        current_app.logger.warning(
            "Login attempt for unknown email hash=%s", _log_email_hash(email)
        )
        return None

    if not user.get('active_status', True):
        verify_password(password, _BASELINE_HASH)   # equalise timing even for inactive accounts
        current_app.logger.warning(
            "Login attempt on deactivated account user_id=%s", user['id']
        )
        raise ValueError("Account deactivated. Please contact your administrator.")

    try:
        if not verify_password(password, user['password_hash']):
            current_app.logger.warning(
                "Failed login — incorrect password user_id=%s", user['id']
            )
            return None
    except Exception as e:
        current_app.logger.error(
            "Security Error: Hash verification failed for user_id=%s: %s", 
            user['id'], e
        )
        return None

    # Successful authentication.
    _rehash_if_needed(user['id'], password, user['password_hash'])
    log_activity(user['id'], "LOGIN", f"User {user['full_name']} logged in")
    log_action(AuditActions.USER_LOGIN, f"Successful login user_id={user['id']}")
    current_app.logger.info("Successful login user_id=%s", user['id'])
    return user


def register_user(
    full_name: str,
    email: str,
    password: str,
    role: str = 'employee',
    job_role: str | None = None,
    **kwargs
) -> tuple[bool, str]:
    """
    Register a new user.

    Enforces a single-admin policy: at most one account with role='admin'
    may exist at any time.

    Returns (True, success_message) or (False, error_message).
    """
    # --- Input validation ---
    if not full_name or not full_name.strip():
        return False, "Full name is required"

    email = email.strip() if email else ""
    if not email:
        return False, "Email is required"
    if not _EMAIL_RE.match(email):
        return False, "Invalid email format"

    if not password or len(password) < _MIN_PW_LENGTH:
        return False, f"Password must be at least {_MIN_PW_LENGTH} characters"

    # --- Business rules ---
    _SELF_REG_ROLES = {'employee', 'manager'}
    if role not in _SELF_REG_ROLES:
        role = 'employee'  # Silent override — backend guardrail, zero UI breakage

    if get_user_by_email(email):
        return False, "An account with this email already exists"

    # --- Persist ---
    try:
        hashed  = hash_password(password)
        user_id = create_user(full_name, email, hashed, role, job_role=job_role, **kwargs)
        current_app.logger.info(
            "New user registered user_id=%s role=%s", user_id, role
        )
        return True, "User registered successfully"
    except ValueError as e:
        return False, str(e)
    except Exception as e:
        current_app.logger.error("Registration error email_hash=%s: %s", _log_email_hash(email), e)
        return False, "Registration failed. Please try again."


def change_user_password(
    user_id: int,
    current_password: str,
    new_password: str,
    confirm_password: str,
) -> tuple[bool, str]:
    """
    Change a user's password after verifying their current one.

    Returns (True, success_message) or (False, error_message).
    """
    if not current_password or not new_password or not confirm_password:
        return False, "All fields are required"

    if new_password != confirm_password:
        return False, "New passwords do not match"

    if len(new_password) < _MIN_PW_LENGTH:
        return False, f"New password must be at least {_MIN_PW_LENGTH} characters"

    user = get_user_by_id(user_id)
    if not user:
        return False, "User not found"

    if not verify_password(current_password, user['password_hash']):
        return False, "Current password is incorrect"

    try:
        update_password_hash(user_id, hash_password(new_password))
        log_activity(user_id, "CHANGE_PASSWORD", "User changed their password")
        current_app.logger.info("Password changed user_id=%s", user_id)
        return True, "Password updated successfully"
    except Exception as e:
        current_app.logger.error("Password change error user_id=%s: %s", user_id, e)
        return False, "An error occurred while updating your password"
