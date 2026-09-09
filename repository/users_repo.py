from .db import execute_query, get_db_cursor
import re
import logging

logger = logging.getLogger(__name__)

ROLE_TABLE_MAP = {
    'admin':           'admins',
    'main_admin':      'admins',
    'secondary_admin': 'admins',
    'manager':         'managers',
    'employee':        'employees',
}

def _get_table_by_role(role_name: str) -> str:
    """Returns target physical table name ('admins', 'managers', 'employees')."""
    return ROLE_TABLE_MAP.get(str(role_name).strip().lower(), 'employees')

def _get_table_by_user_id(user_id: int) -> str:
    """Finds physical table for user_id via unified users view."""
    try:
        res = execute_query("SELECT role FROM users WHERE id = %s", (user_id,), fetch=True)
        if res:
            return _get_table_by_role(res[0]['role'])
    except Exception as e:
        logger.error("Error identifying role table for user %s: %s", user_id, e)
    return 'employees'

def count_admins():
    """Count total number of active admin-level users (main_admin + secondary_admin)."""
    try:
        result = execute_query("SELECT COUNT(*) as count FROM admins WHERE active_status = TRUE", fetch=True)
        return result[0]['count'] if result else 0
    except Exception as e:
        logger.error("Error counting admins: %s", e)
        return 0

def count_main_admins():
    """Count number of active main_admin users. Used to guard the last-main-admin check."""
    try:
        result = execute_query(
            "SELECT COUNT(*) as count FROM admins WHERE role = 'main_admin' AND active_status = TRUE",
            fetch=True
        )
        return result[0]['count'] if result else 0
    except Exception as e:
        logger.error("Error counting main admins: %s", e)
        return 0

def create_user(full_name, email, password_hash, role='employee', job_role=None, avatar_url=None, bio=None, phone=None, city=None, country=None, postal_code=None):
    """Create a new user into their respective physical table (admins, managers, employees)."""
    if not full_name or not full_name.strip():
        raise ValueError("Full name cannot be empty")
    if not email or not email.strip():
        raise ValueError("Email cannot be empty")
    
    email_regex = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    if not re.match(email_regex, email):
        raise ValueError("Invalid email format")
    
    valid_roles = ['employee', 'manager', 'admin', 'main_admin', 'secondary_admin']
    clean_role = str(role).strip().lower()
    if clean_role not in valid_roles:
        raise ValueError(f"Invalid role. Must be one of: {', '.join(valid_roles)}")
    
    target_table = _get_table_by_role(clean_role)

    try:
        with get_db_cursor() as cursor:
            cursor.execute(
                f"""
                INSERT INTO {target_table} (full_name, email, password_hash, role, job_role, avatar_url, bio, phone, city, country, postal_code) 
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) 
                RETURNING id
                """,
                (
                    full_name.strip(), 
                    email.strip().lower(), 
                    password_hash, 
                    clean_role, 
                    job_role,
                    avatar_url,
                    bio,
                    phone,
                    city,
                    country,
                    postal_code
                )
            )
            new_user = cursor.fetchone()
            if new_user:
                u_id = new_user['id']
                login_table = f"{clean_role}_login"
                try:
                    cursor.execute(
                        f"INSERT INTO {login_table} (user_id, email, password_hash) VALUES (%s, %s, %s) "
                        "ON CONFLICT (user_id) DO UPDATE SET email=%s, password_hash=%s",
                        (u_id, email.strip().lower(), password_hash, email.strip().lower(), password_hash)
                    )
                except Exception as log_err:
                    logger.warning("Could not sync %s table: %s", login_table, log_err)
                return u_id
            raise Exception("Failed to retrieve new user ID")
            
    except Exception as e:
        if 'unique constraint' in str(e).lower():
            raise ValueError(f"User with email {email} already exists")
        raise Exception(f"Failed to create user: {str(e)}")

def get_user_by_email(email):
    """Get user by email address across all role tables (via users view)."""
    if not email:
        return None
    
    try:
        users = execute_query("SELECT * FROM users WHERE email = %s", (email.strip().lower(),))
        return users[0] if users else None
    except Exception as e:
        logger.error("Error fetching user by email: %s", e)
        return None

def get_user_by_id(user_id):
    """Get user by ID across all role tables (via users view)."""
    try:
        users = execute_query("SELECT * FROM users WHERE id = %s", (user_id,))
        return users[0] if users else None
    except Exception:
        return None

def get_all_users(active_only=False):
    """Get list of users from the unified users view."""
    sql = "SELECT id, full_name, email, role, active_status, created_at FROM users"
    if active_only:
        sql += " WHERE active_status = TRUE"
    return execute_query(sql)

def update_user(user_id, full_name, email, role, active_status):
    """Update user information across physical tables with role-migration support."""
    if not user_id:
        raise ValueError("User ID is required")
    if not full_name or not full_name.strip():
        raise ValueError("Full name cannot be empty")
    
    valid_roles = ['employee', 'manager', 'admin', 'main_admin', 'secondary_admin']
    clean_role = str(role).strip().lower()
    if clean_role not in valid_roles:
        raise ValueError(f"Invalid role. Must be one of: {', '.join(valid_roles)}")

    current_table = _get_table_by_user_id(user_id)
    target_table = _get_table_by_role(clean_role)

    # If role changed, move record between physical tables
    if current_table != target_table:
        with get_db_cursor() as cursor:
            # Fetch existing profile
            cursor.execute(f"SELECT * FROM {current_table} WHERE id = %s", (user_id,))
            user_data = cursor.fetchone()
            if not user_data:
                raise ValueError(f"User with ID {user_id} not found")

            # Delete from old table
            cursor.execute(f"DELETE FROM {current_table} WHERE id = %s", (user_id,))

            # Insert into new physical role table with same ID
            cursor.execute(
                f"""
                INSERT INTO {target_table} (id, full_name, email, password_hash, role, active_status, created_at, job_role, avatar_url, bio, phone, city, country, postal_code, last_active_at, reliability_score, neural_notifications, neural_auto_analysis, neural_temperature)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    user_id,
                    full_name.strip(),
                    email.strip().lower(),
                    user_data['password_hash'],
                    clean_role,
                    active_status,
                    user_data['created_at'],
                    user_data.get('job_role'),
                    user_data.get('avatar_url'),
                    user_data.get('bio'),
                    user_data.get('phone'),
                    user_data.get('city'),
                    user_data.get('country'),
                    user_data.get('postal_code'),
                    user_data.get('last_active_at'),
                    user_data.get('reliability_score', 100.0),
                    user_data.get('neural_notifications', True),
                    user_data.get('neural_auto_analysis', True),
                    user_data.get('neural_temperature', 0.7)
                )
            )
    else:
        # Standard update in physical table
        row_count = execute_query(
            f"UPDATE {target_table} SET full_name=%s, email=%s, role=%s, active_status=%s WHERE id=%s",
            (full_name.strip(), email.strip().lower(), clean_role, active_status, user_id),
            fetch=False
        )
        if row_count == 0:
            raise ValueError(f"User with ID {user_id} not found")

def soft_delete_user(user_id):
    """Soft delete a user by setting active_status to FALSE in their physical table."""
    if not user_id:
        raise ValueError("User ID is required")
        
    target_table = _get_table_by_user_id(user_id)
    try:
        execute_query(
            f"UPDATE {target_table} SET active_status=FALSE WHERE id=%s",
            (user_id,),
            fetch=False
        )
        logger.info("User %s soft deleted in %s.", user_id, target_table)
        return True
    except Exception as e:
        logger.error("Error soft deleting user %s: %s", user_id, e)
        raise

def update_password_hash(user_id, new_hash):
    """Update password hash in physical role table and login helper table."""
    target_table = _get_table_by_user_id(user_id)
    with get_db_cursor() as cursor:
        cursor.execute(f"UPDATE {target_table} SET password_hash=%s WHERE id=%s RETURNING role", (new_hash, user_id))
        res = cursor.fetchone()
        if res:
            role = res['role'].lower()
            login_table = f"{role}_login"
            try:
                cursor.execute(f"UPDATE {login_table} SET password_hash=%s WHERE user_id=%s", (new_hash, user_id))
            except Exception:
                pass

def update_user_reliability(user_id, score):
    """Update a user's reliability score in their physical table."""
    target_table = _get_table_by_user_id(user_id)
    execute_query(
        f"UPDATE {target_table} SET reliability_score=%s WHERE id=%s",
        (score, user_id),
        fetch=False
    )

def get_avg_reliability():
    """Get average reliability score across all active users from users view."""
    res = execute_query("SELECT AVG(reliability_score) as avg FROM users WHERE active_status = TRUE")
    return res[0]['avg'] if res and res[0]['avg'] else 100.0

def update_user_profile(user_id, **kwargs):
    """Update user profile information in their physical table."""
    if not user_id:
        raise ValueError("User ID is required")

    target_table = _get_table_by_user_id(user_id)
    fields = []
    values = []

    _allowed_fields = [
        'full_name', 'email', 'avatar_url', 'bio', 'phone',
        'city', 'country', 'postal_code',
        'neural_notifications', 'neural_auto_analysis', 'neural_temperature',
    ]

    for key in _allowed_fields:
        if key in kwargs:
            val = kwargs[key]
            if key == 'full_name' and (not val or not val.strip()):
                continue
            if key == 'email' and (not val or not val.strip()):
                continue

            fields.append(f"{key}=%s")
            values.append(val.strip() if isinstance(val, str) else val)

    if not fields:
        return

    values.append(user_id)
    sql = f"UPDATE {target_table} SET {', '.join(fields)} WHERE id=%s"
    execute_query(sql, tuple(values), fetch=False)


def update_last_active(user_id):
    """Update the last_active_at timestamp for a user in their physical table."""
    target_table = _get_table_by_user_id(user_id)
    try:
        execute_query(
            f"UPDATE {target_table} SET last_active_at = NOW() WHERE id = %s",
            (user_id,),
            fetch=False
        )
    except Exception as e:
        logger.debug("Could not update last_active_at for %s: %s", user_id, e)

def get_active_users_count(minutes=5):
    """Get count of users active in the last X minutes."""
    try:
        res = execute_query(
            "SELECT COUNT(*) as count FROM users WHERE last_active_at >= NOW() - make_interval(mins => %s)",
            (int(minutes),),
            fetch=True
        )
        return res[0]['count'] if res else 0
    except Exception as e:
        logger.error("Error counting active users: %s", e)
        return 0

def get_active_user_list(minutes=15):
    """Get list of users active in the last X minutes."""
    try:
        return execute_query(
            "SELECT id, full_name, email, role, last_active_at FROM users WHERE last_active_at >= NOW() - make_interval(mins => %s) ORDER BY last_active_at DESC",
            (int(minutes),),
            fetch=True
        )
    except Exception as e:
        logger.error("Error fetching active users: %s", e)
        return []
