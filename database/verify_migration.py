import os
import sys
from dotenv import load_dotenv
import psycopg2
from psycopg2.extras import RealDictCursor

# Load environment variables
load_dotenv()

def get_db_connection():
    user = os.getenv("DB_USER")
    password = os.getenv("DB_PASSWORD")
    host = os.getenv("DB_HOST")
    port = os.getenv("DB_PORT")
    dbname = os.getenv("DB_NAME")
    
    from urllib.parse import quote_plus
    encoded_password = quote_plus(password)
    url = f"postgresql://{user}:{encoded_password}@{host}:{port}/{dbname}"
    return psycopg2.connect(url)

def verify_schema():
    print("\n🔍 Verifying Database Schema Alignment...")
    print("=" * 60)
    
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        # 1. Check 'users' columns
        cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name = 'users'")
        user_cols = [r['column_name'] for r in cur.fetchall()]
        required_user_cols = ['job_role', 'reliability_score', 'last_active_at']
        user_missing = [c for c in required_user_cols if c not in user_cols]
        
        if not user_missing:
            print("✅ Users table: OK (Found all new columns)")
        else:
            print(f"❌ Users table: MISSING {user_missing}")

        # 2. Check 'tasks' columns
        cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name = 'tasks'")
        task_cols = [r['column_name'] for r in cur.fetchall()]
        required_task_cols = ['complexity', 'predicted_risk', 'category']
        task_missing = [c for c in required_task_cols if c not in task_cols]
        
        if not task_missing:
            print("✅ Tasks table: OK (Found all new columns)")
        else:
            print(f"❌ Tasks table: MISSING {task_missing}")

        # 3. Check for 'user_analytics_summary' table
        cur.execute("SELECT table_name FROM information_schema.tables WHERE table_name = 'user_analytics_summary'")
        if cur.fetchone():
            print("✅ Analytics table: OK (Found 'user_analytics_summary')")
        else:
            print("❌ Analytics table: MISSING 'user_analytics_summary'")

        # 4. Check 'task_statistics' view
        cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name = 'task_statistics'")
        view_cols = [r['column_name'] for r in cur.fetchall()]
        if 'reliability_score' in view_cols:
            print("✅ Task Statistics View: OK (Updated)")
        else:
            print("❌ Task Statistics View: NOT UPDATED")

        cur.close()
        conn.close()
        
        if not user_missing and not task_missing:
            print("\n🎉 SCHEMA IS FULLY ALIGNED!")
            return True
        else:
            print("\n⚠️  SCHEMA MISMATCH DETECTED. Please run the migration script.")
            return False

    except Exception as e:
        print(f"✗ Connection failed: {e}")
        return False

if __name__ == "__main__":
    if verify_schema():
        sys.exit(0)
    else:
        sys.exit(1)
