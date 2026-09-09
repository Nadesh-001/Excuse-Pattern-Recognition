from .db import get_conn
import json

def create_resource(task_id, resource_type, url_or_path, title, ai_summary, requirements_json, deadlines_json, completeness_score):
    conn = get_conn()
    cursor = conn.cursor()
    try:
        if isinstance(requirements_json, dict) or isinstance(requirements_json, list):
             requirements_json = json.dumps(requirements_json)
        if isinstance(deadlines_json, dict) or isinstance(deadlines_json, list):
             deadlines_json = json.dumps(deadlines_json)
             
        cursor.execute(
            """INSERT INTO attachments 
            (task_id, resource_type, url_or_path, title, ai_summary, requirements_json, deadlines_json, completeness_score)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
            (task_id, resource_type, url_or_path, title, ai_summary, requirements_json, deadlines_json, completeness_score)
        )
        conn.commit()
    finally:
        cursor.close()
        conn.close()

def get_resources_by_task(task_id):
    conn = get_conn()
    cursor = conn.cursor()  # PostgreSQL RealDictCursor already set
    try:
        cursor.execute("SELECT * FROM attachments WHERE task_id = %s", (task_id,))
        return cursor.fetchall()
    finally:
        cursor.close()
        conn.close()

def get_all_resources():
    """Get all resources/attachments."""
    conn = get_conn()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT * FROM attachments ORDER BY uploaded_at DESC")
        return cursor.fetchall()
    finally:
        cursor.close()
        conn.close()

def log_resource_access(user_id, attachment_id):
    conn = get_conn()
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO resource_logs (user_id, attachment_id) VALUES (%s, %s)", (user_id, attachment_id))
        conn.commit()
    finally:
        cursor.close()
        conn.close()
