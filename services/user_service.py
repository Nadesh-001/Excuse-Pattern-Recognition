import re
import logging

from repository.users_repo import (
    get_all_users,
    update_user,
    get_user_by_id,
    get_user_by_email,
    create_user,
    soft_delete_user,
    count_main_admins,
)
from utils.hashing import hash_password
from services.activity_service import log_activity

logger = logging.getLogger(__name__)

_EMAIL_RE      = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')
_MIN_PW_LENGTH = 8
_VALID_ROLES   = {'main_admin', 'secondary_admin', 'admin', 'manager', 'employee'}

# Roles that constitute an "admin" for access-level purposes
_ADMIN_ROLE_SET      = {'main_admin', 'secondary_admin', 'admin'}
# Roles a secondary_admin is allowed to assign when creating/editing users
_SECONDARY_ADMIN_CREATABLE = {'manager', 'employee'}
# Roles a main_admin is allowed to assign
_MAIN_ADMIN_CREATABLE      = {'secondary_admin', 'manager', 'employee'}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _get_actor_or_raise(actor_id: int) -> dict:
    """Return the actor dict if they are active, else raise PermissionError."""
    actor = get_user_by_id(actor_id)
    if not actor or not actor.get('active_status', True):
        raise PermissionError("Account inactive or not found")
    return actor


def _require_admin(actor_id: int) -> None:
    """Raise PermissionError if the actor is not an active admin (main or secondary)."""
    actor = _get_actor_or_raise(actor_id)
    if actor.get('role', '').lower() not in _ADMIN_ROLE_SET:
        raise PermissionError("Admin privileges required")


def _require_main_admin(actor_id: int) -> None:
    """Raise PermissionError if the actor is not the main_admin."""
    actor = _get_actor_or_raise(actor_id)
    if actor.get('role', '').lower() != 'main_admin':
        raise PermissionError("Main Admin privileges required")


def _require_manager(actor_id: int) -> None:
    """Raise PermissionError if the actor is not a manager or admin."""
    actor = _get_actor_or_raise(actor_id)
    if actor.get('role', '').lower() not in (_ADMIN_ROLE_SET | {'manager'}):
        raise PermissionError("Manager/Admin privileges required")


def _validate_user_fields(
    full_name: str,
    email: str,
    role: str,
    password: str | None = None,
) -> list[str]:
    """Return a list of validation error messages (empty if all valid)."""
    errors = []

    if not full_name or not full_name.strip():
        errors.append("Full name is required")

    if not email or not _EMAIL_RE.match(email.strip()):
        errors.append("A valid email address is required")

    if role not in _VALID_ROLES:
        errors.append(f"Role must be one of: {', '.join(sorted(_VALID_ROLES))}")

    if password is not None and len(password) < _MIN_PW_LENGTH:
        errors.append(f"Password must be at least {_MIN_PW_LENGTH} characters")

    return errors


def _allowed_roles_for_actor(actor_role: str) -> set:
    """Return the set of roles this actor is permitted to assign."""
    r = actor_role.lower()
    if r == 'main_admin':
        return _MAIN_ADMIN_CREATABLE
    if r in ('secondary_admin', 'admin'):
        return _SECONDARY_ADMIN_CREATABLE
    return set()  # managers / employees cannot assign roles


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_users_list(actor_id: int) -> list[dict]:
    """
    Return all active users for task assignment. Requires the actor to be an admin or manager.
    Note: Managers need this list to assign tasks. Only active users are returned.
    """
    _require_manager(actor_id)
    return get_all_users(active_only=True)


def manage_create_user(
    actor_id: int,
    full_name: str,
    email: str,
    password: str,
    role: str,
) -> tuple[bool, str]:
    """Create a new user. Actor must be an admin (main or secondary).

    Role-creation boundaries:
    - main_admin    → may create secondary_admin, manager, employee
    - secondary_admin → may create manager, employee only
    - Neither may create another main_admin through this function.
    """
    try:
        actor = _get_actor_or_raise(actor_id)
        actor_role = actor.get('role', '').lower()
        if actor_role not in _ADMIN_ROLE_SET:
            return False, "Admin privileges required"
    except PermissionError as e:
        return False, str(e)

    clean_role = role.strip().lower() if role else ''
    allowed_roles = _allowed_roles_for_actor(actor_role)
    if clean_role not in allowed_roles:
        role_list = ', '.join(sorted(allowed_roles))
        return False, f"You are not permitted to create a user with role '{clean_role}'. Allowed: {role_list}"

    email = email.strip()
    errors = _validate_user_fields(full_name, email, clean_role, password)
    if errors:
        return False, "; ".join(errors)

    if get_user_by_email(email):
        return False, "An account with this email already exists"

    try:
        create_user(full_name.strip(), email, hash_password(password), clean_role)
        log_activity(actor_id, "CREATE_USER", f"Created user {email} role={clean_role} by actor_id={actor_id}")
        return True, "User created successfully"
    except Exception as e:
        logger.error("manage_create_user failed for email=%s: %s", email, e)
        return False, "User creation failed. Please try again."


def manage_update_user(
    actor_id: int,
    target_user_id: int,
    full_name: str,
    email: str,
    role: str,
    active_status: bool,
) -> tuple[bool, str]:
    """Update an existing user's details. Actor must be an admin (main or secondary).

    Role-transition boundaries:
    - main_admin    → may assign secondary_admin, manager, employee
    - secondary_admin → may assign manager, employee only
    """
    try:
        actor = _get_actor_or_raise(actor_id)
        actor_role = actor.get('role', '').lower()
        if actor_role not in _ADMIN_ROLE_SET:
            return False, "Admin privileges required"
    except PermissionError as e:
        return False, str(e)

    clean_role = role.strip().lower() if role else ''
    allowed_roles = _allowed_roles_for_actor(actor_role)
    if clean_role not in allowed_roles:
        role_list = ', '.join(sorted(allowed_roles))
        return False, f"You are not permitted to assign role '{clean_role}'. Allowed: {role_list}"

    email = email.strip()
    errors = _validate_user_fields(full_name, email, clean_role)
    if errors:
        return False, "; ".join(errors)

    existing = get_user_by_email(email)
    if existing and existing['id'] != target_user_id:
        return False, "Email is already in use by another account"

    try:
        update_user(target_user_id, full_name.strip(), email, clean_role, active_status)
        log_activity(
            actor_id, "UPDATE_USER",
            f"Updated user_id={target_user_id} email={email} role={clean_role} active={active_status}"
        )
        return True, "User updated successfully"
    except Exception as e:
        logger.error("manage_update_user failed for user_id=%s: %s", target_user_id, e)
        return False, "User update failed. Please try again."


def service_delete_own_account(user_id: int) -> tuple[bool, str]:
    """Soft-delete the requesting user's own account."""
    try:
        soft_delete_user(user_id)
        log_activity(user_id, "DELETE_ACCOUNT", "User deleted their own account")
        return True, "Account deleted successfully"
    except LookupError:
        return False, "Account not found"
    except Exception as e:
        logger.error("service_delete_own_account failed for user_id=%s: %s", user_id, e)
        return False, "Account deletion failed. Please try again."

def get_user_momentum(user_id: int) -> dict:
    """
    Fetch live behavioral momentum signals for display on the profile page.
    Returns drift, velocity state, burst count, and overall momentum direction.
    """
    from database.connection import get_db_cursor
    result = {
        'risk_drift':           None,    # float: recent - lifetime avg
        'escalation_velocity':  'unknown',
        'recent_scores':        [],      # last 4 risk scores (DESC)
        'burst_count_14d':      0,
        'momentum_dir':         'neutral',  # 'worsening' | 'improving' | 'stable' | 'neutral'
    }
    try:
        with get_db_cursor() as cur:
            # Signal 1: drift
            cur.execute(
                """SELECT
                       AVG(CASE WHEN recorded_at > NOW() - INTERVAL '30 days'
                                THEN risk_score END)  AS recent_avg,
                       AVG(risk_score)                AS lifetime_avg,
                       COUNT(*)                       AS total_entries
                   FROM risk_history WHERE user_id = %s""",
                (user_id,)
            )
            row = cur.fetchone()
            if row and row['recent_avg'] is not None:
                drift = float(row['recent_avg']) - float(row['lifetime_avg'])
                result['risk_drift']    = round(drift, 2)
                result['total_entries'] = int(row['total_entries'] or 0)
                if drift > 8:
                    result['momentum_dir'] = 'worsening_fast'
                elif drift > 4:
                    result['momentum_dir'] = 'worsening'
                elif drift < -5:
                    result['momentum_dir'] = 'improving'
                else:
                    result['momentum_dir'] = 'stable'

            # Signal 2: escalation velocity
            cur.execute(
                """SELECT risk_score FROM risk_history
                   WHERE user_id = %s ORDER BY recorded_at DESC LIMIT 4""",
                (user_id,)
            )
            scores = [r['risk_score'] for r in cur.fetchall()]
            result['recent_scores'] = scores
            if len(scores) >= 3:
                result['escalation_velocity'] = (
                    'spiral' if scores[0] > scores[1] > scores[2] else 'stable'
                )

            # Signal 3: deadline burst
            cur.execute(
                """SELECT COUNT(*) AS burst_count FROM delays
                   WHERE user_id = %s AND submitted_at > NOW() - INTERVAL '14 days'""",
                (user_id,)
            )
            burst = cur.fetchone()
            result['burst_count_14d'] = int(burst['burst_count'] or 0) if burst else 0

    except Exception as e:
        logger.warning("get_user_momentum failed user_id=%s: %s", user_id, e)
    return result


def get_user_integrity_stats(user_id: int) -> dict:
    """
    Fetch Tier 3 Manipulation Resistance stats (Entropy, Reputation, Recycled Flags).
    Aggregates data from the last 10 delays.
    """
    from database.connection import get_db_cursor
    import json
    
    stats = {
        'avg_entropy':      0.0,
        'flags_triggered':  0,
        'recycled_proofs':  0,
        'template_matches': 0,
        'integrity_label':  'Stable'
    }
    
    try:
        with get_db_cursor() as cur:
            cur.execute(
                """SELECT ai_analysis_json FROM delays 
                   WHERE user_id = %s ORDER BY submitted_at DESC LIMIT 10""",
                (user_id,)
            )
            rows = cur.fetchall()
            
            if not rows:
                return stats
                
            total_entropy = 0
            count = 0
            
            for row in rows:
                analysis = row['ai_analysis_json']
                if isinstance(analysis, str):
                    try: analysis = json.loads(analysis)
                    except: analysis = {}
                
                # Signal 1: Entropy
                if 'entropy' in analysis:
                    total_entropy += float(analysis['entropy'])
                    count += 1
                
                # Signal 2: Flags
                flags = analysis.get('manipulation_flags', [])
                stats['flags_triggered'] += len(flags)
                if 'RECYCLED_EVIDENCE' in flags: stats['recycled_proofs'] += 1
                if 'STRUCTURAL_REPETITION' in flags: stats['template_matches'] += 1
                
            if count > 0:
                stats['avg_entropy'] = round(total_entropy / count, 2)
            
            # Labeling
            if stats['recycled_proofs'] > 0 or stats['template_matches'] > 1:
                stats['integrity_label'] = 'Compromised'
            elif stats['flags_triggered'] > 2 or (count > 2 and stats['avg_entropy'] < 3.0):
                stats['integrity_label'] = 'Suspicious'
            elif stats['flags_triggered'] > 0:
                stats['integrity_label'] = 'Warning'
                
    except Exception as e:
        logger.warning("get_user_integrity_stats failed user_id=%s: %s", user_id, e)
        
    return stats


def get_user_baseline(user_id: int) -> dict:

    """Fetch user's personal scoring baseline from user_analytics_summary."""
    from repository.db import execute_query
    try:
        rows = execute_query(
            """SELECT avg_authenticity, std_authenticity, avg_avoidance,
                      std_avoidance, delay_count_total
               FROM user_analytics_summary
               WHERE user_id = %s""",
            (user_id,), fetch=True
        )
        if rows:
            return {
                'avg_auth':   float(rows[0].get('avg_authenticity') or 0),
                'std_auth':   float(rows[0].get('std_authenticity') or 0),
                'avg_avoid':  float(rows[0].get('avg_avoidance') or 0),
                'std_avoid':  float(rows[0].get('std_avoidance') or 0),
                'count':      int(rows[0].get('delay_count_total') or 0),
            }
    except Exception as e:
        logger.warning("get_user_baseline failed user_id=%s: %s", user_id, e)
    return {'avg_auth': 0, 'std_auth': 0, 'avg_avoid': 0, 'std_avoid': 0, 'count': 0}


def update_user_baseline(user_id: int, new_auth: float, new_avoid: float) -> None:
    """
    Incrementally update avg and std dev using Welford's online algorithm.
    Never rescans history — O(1) update per delay submission.
    """
    from database.connection import get_db_cursor
    import math
    try:
        with get_db_cursor() as cur:
            # Fetch existing Welford state
            cur.execute(
                """SELECT delay_count_total, avg_authenticity, auth_M2,
                          avg_avoidance, avoid_M2
                   FROM user_analytics_summary WHERE user_id = %s""",
                (user_id,)
            )
            row = cur.fetchone()

            if row:
                n       = int(row['delay_count_total'] or 0)
                mean_a  = float(row['avg_authenticity'] or 0)
                M2_a    = float(row['auth_M2'] or 0)
                mean_av = float(row['avg_avoidance'] or 0)
                M2_av   = float(row['avoid_M2'] or 0)
            else:
                n, mean_a, M2_a, mean_av, M2_av = 0, 0.0, 0.0, 0.0, 0.0

            # Welford update
            n       += 1
            delta_a  = new_auth  - mean_a
            mean_a  += delta_a  / n
            M2_a    += delta_a  * (new_auth  - mean_a)

            delta_av = new_avoid - mean_av
            mean_av += delta_av / n
            M2_av   += delta_av * (new_avoid - mean_av)

            # Sample Standard Deviation (n-1) for unbiased estimation
            # Governance Level D+: Quant-Grade Statistical Modeling
            std_a  = math.sqrt(M2_a  / (n - 1)) if n > 1 else 0.0
            std_av = math.sqrt(M2_av / (n - 1)) if n > 1 else 0.0

            cur.execute(
                """INSERT INTO user_analytics_summary
                       (user_id, avg_authenticity, std_authenticity, auth_M2,
                        avg_avoidance, std_avoidance, avoid_M2, delay_count_total)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                   ON CONFLICT (user_id) DO UPDATE SET
                       avg_authenticity  = EXCLUDED.avg_authenticity,
                       std_authenticity  = EXCLUDED.std_authenticity,
                       auth_M2           = EXCLUDED.auth_M2,
                       avg_avoidance     = EXCLUDED.avg_avoidance,
                       std_avoidance     = EXCLUDED.std_avoidance,
                       avoid_M2          = EXCLUDED.avoid_M2,
                       delay_count_total = EXCLUDED.delay_count_total,
                       last_updated      = NOW()""",
                (user_id, round(mean_a, 4), round(std_a, 4), round(M2_a, 4),
                 round(mean_av, 4), round(std_av, 4), round(M2_av, 4), n)
            )
    except Exception as e:
        logger.warning("update_user_baseline failed user_id=%s: %s", user_id, e)


def get_user_short_term_baseline(user_id: int) -> dict:
    """
    Calculate high-resolution baseline using last 10 risk scores.
    Weighting favors recent entries (Exponentially Weighted).
    """
    from database.connection import get_db_cursor
    try:
        with get_db_cursor() as cur:
            cur.execute(
                """
                SELECT rh.risk_score 
                FROM risk_history rh
                JOIN tasks t ON rh.task_id = t.id
                WHERE t.assigned_to = %s
                ORDER BY rh.recorded_at DESC
                LIMIT 10
                """,
                (user_id,)
            )
            scores = [float(r['risk_score']) for r in cur.fetchall()]
            
            if not scores:
                return {'short_term_avg': 0, 'sample_size': 0, 'trend': 'neutral'}
            
            # Simple weighted avg: (4*s0 + 3*s1 + 2*s2 + 1*s3...)
            weights = list(range(len(scores), 0, -1))
            weighted_sum = sum(s * w for s, w in zip(scores, weights))
            avg = round(weighted_sum / sum(weights), 2)
            
            trend = 'neutral'
            if len(scores) >= 3:
                if scores[0] > scores[1] > scores[2]: trend = 'deteriorating'
                elif scores[0] < scores[1] < scores[2]: trend = 'improving'
                
            return {
                'short_term_avg': avg,
                'sample_size': len(scores),
                'trend': trend,
                'last_score': scores[0]
            }
    except Exception as e:
        logger.warning("get_user_short_term_baseline failed for user %s: %s", user_id, e)
    return {'short_term_avg': 0, 'sample_size': 0, 'trend': 'neutral'}


def compute_behavioral_state(user_id: int) -> dict:
    """
    Statistical Behavioral State classification.
    Classifies into: STABLE, DRIFTING, HIGH_RISK, RECOVERING.
    Governance Level D+: Quant-Grade Statistical Modeling.
    """
    from database.connection import get_db_cursor
    try:
        with get_db_cursor() as cur:
            # 1. Fetch User Baseline Metrics
            cur.execute(
                "SELECT avg_avoidance, std_avoidance, delay_count_total FROM user_analytics_summary WHERE user_id = %s",
                (user_id,)
            )
            baseline = cur.fetchone()
            b_mean = float(baseline['avg_avoidance'] or 50) if baseline else 50
            b_std  = float(baseline['std_avoidance'] or 15) if baseline else 15
            b_std  = max(2.0, b_std) # Min floor for stability

            # 2. Fetch Recent Risk History
            cur.execute(
                """
                SELECT rh.risk_score 
                FROM risk_history rh
                JOIN tasks t ON rh.task_id = t.id
                WHERE t.assigned_to = %s
                ORDER BY rh.recorded_at DESC
                LIMIT 15
                """,
                (user_id,)
            )
            rows = cur.fetchall()
            scores = [float(r['risk_score']) for r in rows]
            
            # Maturity Check: Statistical significance requires at least 5 baseline entries
            # and 3 recent task entries.
            n_total = int(baseline['delay_count_total'] or 0) if baseline else 0
            if n_total < 5 or len(scores) < 3:
                return {'state': 'STABLE', 'confidence': 'low', 'z_score': 0, 'signal': 'maturing'}
            
            recent_avg = sum(scores[:3]) / 3.0
            
            # 3. Z-Score Statistical Evaluation
            z_score = (recent_avg - b_mean) / b_std
            
            # 4. State Assignment
            # High Risk: Extreme Z (>3) OR sustained high absolute risk
            if z_score > 3.0 or recent_avg > 80:
                return {'state': 'HIGH_RISK', 'confidence': 'high', 'z_score': round(z_score, 2)}
                
            # Drifting: Statistical deviation > 2.0 (95% confidence)
            if z_score > 2.0:
                return {'state': 'DRIFTING', 'confidence': 'medium', 'z_score': round(z_score, 2)}
                
            # Recovering: Improving significantly from high baseline
            if z_score < -1.5 and b_mean > 50:
                return {'state': 'RECOVERING', 'confidence': 'medium', 'z_score': round(z_score, 2)}
                
            return {'state': 'STABLE', 'confidence': 'high', 'z_score': round(z_score, 2)}
            
    except Exception as e:
        logger.error("compute_behavioral_state failed for user %s: %s", user_id, e)
    return {'state': 'UNKNOWN', 'confidence': 'zero', 'signal': 'error'}
def batch_compute_behavioral_states() -> dict:
    """
    Tier 5: Efficiently compute behavioral states for all users.
    Uses Statistical Z-score deviation against personal baselines.
    """
    from database.connection import get_db_cursor
    
    try:
        with get_db_cursor() as cur:
            # Optimized Window Function query + join with baselines
            cur.execute(
                """
                WITH RankedHistory AS (
                    SELECT rh.risk_score, t.assigned_to as user_id,
                           ROW_NUMBER() OVER(PARTITION BY t.assigned_to ORDER BY rh.recorded_at DESC) as rank
                    FROM risk_history rh
                    JOIN tasks t ON rh.task_id = t.id
                ),
                RecentStats AS (
                    SELECT user_id, AVG(risk_score) as recent_avg
                    FROM RankedHistory WHERE rank <= 3
                    GROUP BY user_id
                )
                SELECT 
                    rs.user_id, 
                    rs.recent_avg,
                    uas.avg_avoidance as b_mean,
                    uas.std_avoidance as b_std
                FROM RecentStats rs
                LEFT JOIN user_analytics_summary uas ON rs.user_id = uas.user_id;
                """
            )
            rows = cur.fetchall()
            
            results = {}
            for row in rows:
                u_id = row['user_id']
                recent_avg = float(row['recent_avg'])
                b_mean = float(row['b_mean'] or 50)
                b_std  = float(row['b_std'] or 15)
                b_std  = max(2.0, b_std)
                
                z = (recent_avg - b_mean) / b_std
                
                if z > 3.0 or recent_avg > 80: state = 'HIGH_RISK'
                elif z > 2.0: state = 'DRIFTING'
                elif z < -1.5 and b_mean > 50: state = 'RECOVERING'
                else: state = 'STABLE'
                
                results[u_id] = {'state': state, 'z_score': round(z, 2)}
            
            return results
    except Exception as e:
        logger.error("batch_compute_behavioral_states failed: %s", e)
        return {}
def refresh_user_reliability(user_id: int) -> dict:
    """
    Orchestrates the update of user-level behavioral aggregates.
    Called after every task submission or completion.
    Governance Level C: Behavioral Modeling.
    """
    try:
        from database.connection import get_db_cursor
        
        # 1. Update Welford Baseline (O(1))
        # We need the last risk score to update the baseline efficiently
        with get_db_cursor() as cur:
            cur.execute(
                "SELECT risk_score FROM risk_history WHERE user_id = %s ORDER BY recorded_at DESC LIMIT 1",
                (user_id,)
            )
            row = cur.fetchone()
            if row:
                risk = float(row['risk_score'])
                update_user_baseline(user_id, 100 - risk, risk) # Auth = 100 - Risk

        # 2. Compute Current Behavioral State (Classification)
        state_data = compute_behavioral_state(user_id)
        
        # 3. Update Profile View Cache or Summary Table if needed
        # (Already handled by on-the-fly analytics in analytics_service)
        
        return state_data
    except Exception as e:
        logger.error("refresh_user_reliability failed for user %s: %s", user_id, e)
        return {'state': 'UNKNOWN', 'error': str(e)}
