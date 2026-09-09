import sys
import os
sys.path.append(os.getcwd())
from database.connection import execute_query

def run_migration():
    print("🚀 Running Performance Index Migration...")
    
    queries = [
        """
        CREATE INDEX IF NOT EXISTS idx_tasks_assigned_created 
        ON tasks (assigned_to, created_at DESC);
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_delays_user_submitted 
        ON delays (user_id, submitted_at DESC);
        """
    ]
    
    for q in queries:
        try:
            execute_query(q, fetch=False)
            print(f"✅ Executed: {q.strip().splitlines()[0]}")
        except Exception as e:
            print(f"❌ Error: {e}")

if __name__ == "__main__":
    run_migration()
