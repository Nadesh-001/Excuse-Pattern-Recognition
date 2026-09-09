import sys
sys.path.insert(0, '.')
from database.connection import execute_query, test_connection
import json

# Full connection test
result = test_connection()
print(json.dumps(result, indent=2))

# Table list
rows = execute_query(
    "SELECT table_name FROM information_schema.tables "
    "WHERE table_schema='public' AND table_type='BASE TABLE' ORDER BY table_name"
)
print(f"\nTables found: {len(rows)}")
for r in rows:
    print(f"  [OK] {r['table_name']}")
