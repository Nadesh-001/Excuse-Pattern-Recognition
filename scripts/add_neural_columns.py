"""
Migration script to add neural settings columns to the users table.
"""
import os
import sys

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from repository.db import execute_query

def migrate():
    print("🚀 Starting migration: Adding neural settings columns...")
    
    queries = [
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS neural_notifications BOOLEAN DEFAULT TRUE;",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS neural_auto_analysis BOOLEAN DEFAULT TRUE;",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS neural_temperature FLOAT DEFAULT 0.7;"
    ]
    
    try:
        for query in queries:
            execute_query(query, fetch=False)
            print(f"✅ Executed: {query.strip()}")
        print("🎉 Migration completed successfully.")
    except Exception as e:
        print(f"❌ Migration failed: {e}")

if __name__ == "__main__":
    migrate()
