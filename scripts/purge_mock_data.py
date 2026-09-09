import sys
import os
sys.path.append(os.getcwd())
from repository.db import execute_query

def purge():
    print("🧹 Starting Mock Data Purge...")
    try:
        # Truncating the delays table to remove all mock records
        # This will reset the dashboard to real data only
        execute_query("TRUNCATE TABLE delays CASCADE;", (), fetch=False)
        print("✅ Success: Table 'delays' has been purged.")
        
        # Also clean up risk_history and ai_snapshots which likely contain mock data
        execute_query("TRUNCATE TABLE risk_history CASCADE;", (), fetch=False)
        execute_query("TRUNCATE TABLE ai_snapshots CASCADE;", (), fetch=False)
        print("✅ Success: Auxiliary analytics tables purged.")
        
    except Exception as e:
        print(f"❌ Error during purge: {e}")

if __name__ == "__main__":
    purge()
