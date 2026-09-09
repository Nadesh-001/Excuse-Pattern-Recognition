from .db import execute_query, get_db_cursor
import json
import logging

logger = logging.getLogger(__name__)

def get_delays_all():
    query = """
        SELECT d.*, t.title as task_title, u.email as user_email
        FROM delays d
        LEFT JOIN tasks t ON d.task_id = t.id
        LEFT JOIN users u ON d.user_id = u.id
        ORDER BY d.submitted_at DESC
    """
    return execute_query(query)

def create_delay(task_id, user_id, reason_text, reason_audio_path, score_authenticity, score_avoidance, risk_level, ai_feedback, ai_analysis_json, delay_duration=0, proof_path=None):
    """Create delay record with validation."""
    try:
        # Ensure json is stringified for JSONB column or just passed as dict (psycopg2 handles dict to jsonb automatically often, but explicit dumps is safer for text fields)
        if isinstance(ai_analysis_json, dict):
            ai_analysis_json = json.dumps(ai_analysis_json)
            
        with get_db_cursor() as cursor:
            cursor.execute("""
                INSERT INTO delays (task_id, user_id, reason_text, reason_audio_path, score_authenticity, score_avoidance, risk_level, ai_feedback, ai_analysis_json, delay_duration, proof_path)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
            """, (task_id, user_id, reason_text.strip(), reason_audio_path, score_authenticity, score_avoidance, risk_level, ai_feedback, ai_analysis_json, delay_duration, proof_path))

            # fetchone() MUST be called to retrieve the RETURNING clause
            result = cursor.fetchone()

            if result:
                # Handle both RealDictRow and plain tuple cursor types
                if isinstance(result, dict):
                    delay_id = result.get('id')
                else:
                    delay_id = result[0]

                logger.info("Created delay ID: %s", delay_id)
                return delay_id
            else:
                raise Exception("INSERT succeeded but RETURNING id returned no row")
            
    except Exception as e:
        logger.exception("CREATE_DELAY ERROR: %s", e)
        raise

    return execute_query(query)

def get_delay_by_id(delay_id):
    """Fetch a specific delay record by ID."""
    query = "SELECT * FROM delays WHERE id = %s"
    result = execute_query(query, (delay_id,))
    return result[0] if result else None

def get_delays_by_task(task_id):
    query = """
        SELECT d.*, u.full_name as user_name, u.email as user_email
        FROM delays d
        LEFT JOIN users u ON d.user_id = u.id
        WHERE d.task_id = %s
        ORDER BY d.submitted_at DESC
    """
    return execute_query(query, (task_id,))

def get_delays_by_user(user_id):
    query = """
        SELECT d.*, t.title as task_title 
        FROM delays d
        LEFT JOIN tasks t ON d.task_id = t.id
        WHERE d.user_id = %s
        ORDER BY d.submitted_at DESC
    """
    return execute_query(query, (user_id,))

def get_user_delay_history(user_id, limit=5):
    """Formula 10: Get recent delays for behavioral consistency."""
    try:
        return execute_query("""
            SELECT 
                d.id, 
                d.reason_text, 
                d.score_authenticity, 
                d.score_avoidance, 
                d.risk_level, 
                d.ai_analysis_json, 
                d.delay_duration, 
                d.submitted_at,
                t.deadline
            FROM delays d
            LEFT JOIN tasks t ON d.task_id = t.id
            WHERE d.user_id = %s
            ORDER BY d.submitted_at DESC
            LIMIT %s
        """, (user_id, limit))
    except Exception as e:
        logger.error("Error fetching delay history for user %s: %s", user_id, e)
        return []

def count_user_delays(user_id):
    """Formula 5: Count total delays for employee."""
    try:
        result = execute_query("SELECT COUNT(*) as count FROM delays WHERE user_id = %s", (user_id,), fetch=True)
        return result[0]['count'] if result else 0
    except Exception as e:
        logger.error("Error counting delays for user %s: %s", user_id, e)
        return 0

def delete_delay(delay_id):
    """Delete a delay record by ID. Returns affected row count."""
    try:
        query = "DELETE FROM delays WHERE id = %s"
        return execute_query(query, (delay_id,), fetch=False)
    except Exception as e:
        logger.error("Error deleting delay %s: %s", delay_id, e)
        return 0

# Alias for compatibility
def get_all_delays():
    """Alias for get_delays_all for compatibility."""
    return get_delays_all()
