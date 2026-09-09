import sys
import os
sys.path.append(os.getcwd())
from database.connection import DatabaseConnection, get_db_cursor

def setup():
    print("🚀 Initializing Production Hardening...")
    
    # 1. Ensure Pool
    try:
        if not DatabaseConnection.get_pool():
            DatabaseConnection.initialize_pool()
    except Exception as e:
        print(f"❌ Failed to initialize DB pool: {e}")
        return

    # 2. Run Migrations
    migrations = [
        "database/migrations/performance_indexes.sql",
    ]
    
    with get_db_cursor() as cur:
        # Fix risk_history schema
        print("🔧 Repairing risk_history schema...")
        cur.execute("ALTER TABLE risk_history ADD COLUMN IF NOT EXISTS user_id INTEGER;")
        
        # Create AI Snapshot table
        print("📁 Creating snapshot tables...")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS ai_snapshots (
                id SERIAL PRIMARY KEY,
                user_id INTEGER,
                role VARCHAR(50),
                summary_json JSONB,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        
        cur.execute("""
            CREATE TABLE IF NOT EXISTS system_health_snapshots (
                id SERIAL PRIMARY KEY,
                snapshot_json JSONB,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        
        # Apply performance indexes
        for migration in migrations:
            print(f"📄 Applying {migration}...")
            if os.path.exists(migration):
                with open(migration, 'r') as f:
                    # Execute semicolon-separated commands individually to avoid multi-statement issues
                    commands = f.read().split(';')
                    for cmd in commands:
                        if cmd.strip():
                            cur.execute(cmd)
            else:
                print(f"⚠️ Warning: migration file {migration} not found.")

    print("✅ Production Hardening Complete.")

if __name__ == "__main__":
    setup()
