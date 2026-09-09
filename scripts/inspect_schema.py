import sys
import os
sys.path.append(os.getcwd())
from database.connection import get_db_cursor

def inspect_schema():
    tables = ['risk_history', 'ai_snapshots']
    for table in tables:
        print(f"\n🔍 Inspecting table: {table}")
        try:
            with get_db_cursor() as cur:
                cur.execute(f"SELECT column_name, data_type FROM information_schema.columns WHERE table_name = '{table}'")
                cols = cur.fetchall()
                if not cols:
                    print(f"  ⚠️ Table '{table}' does not exist or has no columns.")
                else:
                    for col in cols:
                        print(f"  - {col['column_name']} ({col['data_type']})")
        except Exception as e:
            print(f"  ❌ Error: {e}")

if __name__ == "__main__":
    inspect_schema()
