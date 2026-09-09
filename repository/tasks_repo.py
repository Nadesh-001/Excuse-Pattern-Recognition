from .db import execute_query, get_db_cursor
import logging

logger = logging.getLogger(__name__)

def create_task(title, description, assigned_to, created_by, priority, deadline, estimated_minutes, complexity=1, predicted_risk=0, risk_factors=None, category='General'):
    try:
        import json
        with get_db_cursor() as cursor:
            cursor.execute(
                """INSERT INTO tasks 
                   (title, description, assigned_to, created_by, status, priority, deadline, estimated_minutes, complexity, predicted_risk, risk_factors, category) 
                   VALUES (%s, %s, %s, %s, 'Pending', %s, %s, %s, %s, %s, %s, %s) 
                   RETURNING id""",
                (title, description, assigned_to, created_by, priority, deadline, estimated_minutes, complexity, predicted_risk, json.dumps(risk_factors or {}), category)
            )
            result = cursor.fetchone()
            if result:
                return result['id']
            raise Exception("Failed to get new task ID")
    except Exception as e:
        logger.error("Error creating task: %s", e)
        raise

def get_tasks_by_user(user_id):
    query = """
        SELECT id, title, description, assigned_to, created_by, status, 
               priority, deadline, estimated_minutes, created_at,
               predicted_risk AS risk_score
        FROM tasks 
        WHERE assigned_to = %s 
        ORDER BY created_at DESC
    """
    return execute_query(query, (user_id,)) or []

def get_all_tasks():
    query = """
        SELECT 
            t.id, t.title, t.description, t.assigned_to, t.created_by, 
            t.status, t.priority, t.deadline, t.estimated_minutes, t.created_at,
            t.predicted_risk AS risk_score,
            u_assign.email as assigned_to_email, 
            u_create.email as created_by_email 
        FROM tasks t
        LEFT JOIN users u_assign ON t.assigned_to = u_assign.id
        LEFT JOIN users u_create ON t.created_by = u_create.id
        ORDER BY t.created_at DESC
    """
    return execute_query(query) or []

def update_task_status(task_id, status):
    execute_query(
        "UPDATE tasks SET status=%s WHERE id=%s", 
        (status, task_id), 
        fetch=False
    )

def get_task_by_id(task_id):
    """Get task details by ID."""
    if not task_id:
        return None
        
    query = """
        SELECT id, title, description, assigned_to, created_by, status, 
               priority, deadline, estimated_minutes, created_at, completion_timestamp,
               predicted_risk AS risk_score
        FROM tasks 
        WHERE id = %s
    """
    results = execute_query(query, (task_id,))
    return results[0] if results else None

def update_task_completion(task_id, completion_timestamp, status):
    """Update task with completion details."""
    row_count = execute_query(
        """
        UPDATE tasks 
        SET completion_timestamp = %s, status = %s
        WHERE id = %s
        """, 
        (completion_timestamp, status, task_id),
        fetch=False
    )
    
    if row_count == 0:
        raise ValueError(f"Task {task_id} not found")
    
    logger.info("Task %s status updated: %s", task_id, status)

def delete_task(task_id):
    """Permanently delete a task."""
    execute_query(
        "DELETE FROM tasks WHERE id = %s",
        (task_id,),
        fetch=False
    )
    logger.info("Task %s deleted", task_id)

def count_user_tasks(user_id):
    """Count total tasks assigned to a user."""
    query = "SELECT COUNT(*) as count FROM tasks WHERE assigned_to = %s"
    result = execute_query(query, (user_id,))
    return result[0]['count'] if result else 0

def update_task_risk(task_id, risk_score, risk_factors):
    """Update task with predictive risk data."""
    import json
    execute_query(
        "UPDATE tasks SET predicted_risk = %s, risk_factors = %s WHERE id = %s",
        (risk_score, json.dumps(risk_factors), task_id),
        fetch=False
    )
