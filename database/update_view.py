import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()

def update_view():
    user = os.getenv("DB_USER")
    password = os.getenv("DB_PASSWORD")
    host = os.getenv("DB_HOST")
    port = os.getenv("DB_PORT")
    dbname = os.getenv("DB_NAME")
    
    from urllib.parse import quote_plus
    encoded_password = quote_plus(password)
    url = f"postgresql://{user}:{encoded_password}@{host}:{port}/{dbname}"
    
    sql = """
    DROP VIEW IF EXISTS task_statistics;
    CREATE VIEW task_statistics AS
    SELECT 
        u.id as user_id,
        u.full_name,
        u.email,
        u.role,
        u.reliability_score,
        COUNT(t.id) as total_tasks,
        COUNT(CASE WHEN t.status = 'Completed' THEN 1 END) as completed_tasks,
        COUNT(CASE WHEN t.status = 'Delayed' THEN 1 END) as delayed_tasks,
        COUNT(CASE WHEN t.status = 'Pending' THEN 1 END) as pending_tasks,
        COUNT(d.id) as total_delays,
        AVG(d.score_authenticity) as avg_authenticity_score
    FROM users u
    LEFT JOIN tasks t ON t.assigned_to = u.id
    LEFT JOIN delays d ON d.user_id = u.id
    GROUP BY u.id, u.full_name, u.email, u.role, u.reliability_score;

    ALTER VIEW task_statistics SET (security_invoker = true);
    """
    
    try:
        conn = psycopg2.connect(url)
        conn.autocommit = True
        cur = conn.cursor()
        print("🚀 Updating task_statistics view...")
        cur.execute(sql)
        print("✅ View updated successfully!")
        cur.close()
        conn.close()
        return True
    except Exception as e:
        print(f"❌ Failed to update view: {e}")
        return False

if __name__ == "__main__":
    update_view()
