"""
Backfill existing users into their role-specific login tables.
"""
import sys
sys.path.insert(0, '.')
from database.startup_checks import run_startup_checks
from database.connection import get_db_cursor

def backfill():
    # Ensure tables are created
    run_startup_checks()
    
    with get_db_cursor() as cur:
        cur.execute("SELECT id, email, password_hash, role FROM users")
        users = cur.fetchall()
        for u in users:
            role = u['role'].lower()
            if role in ('admin', 'manager', 'employee'):
                table = f"{role}_login"
                cur.execute(
                    f"INSERT INTO {table} (user_id, email, password_hash) VALUES (%s, %s, %s) "
                    "ON CONFLICT (user_id) DO UPDATE SET email=%s, password_hash=%s",
                    (u['id'], u['email'], u['password_hash'], u['email'], u['password_hash'])
                )
                print(f"Backfilled user {u['email']} into {table}")

if __name__ == "__main__":
    backfill()
