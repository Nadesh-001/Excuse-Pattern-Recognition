"""
Reset admin credentials on AWS RDS.
Removes all users and related data, then creates a fresh admin account.
"""
import sys
sys.path.insert(0, '.')

from database.connection import get_db_cursor
import bcrypt

EMAIL    = "admin@excuseai.com"
PASSWORD = "Admin@2026"
NAME     = "Admin"

# Hash password
hashed = bcrypt.hashpw(PASSWORD.encode(), bcrypt.gensalt(12)).decode()

with get_db_cursor() as cur:
    # Clear all users and cascade to related tables
    cur.execute("TRUNCATE TABLE users RESTART IDENTITY CASCADE")
    print("All existing users and related data removed.")

    # Insert fresh admin
    cur.execute(
        """
        INSERT INTO users (full_name, email, password_hash, role, active_status)
        VALUES (%s, %s, %s, 'admin', TRUE)
        RETURNING id
        """,
        (NAME, EMAIL, hashed)
    )
    new_id = cur.fetchone()['id']
    print(f"\nNew admin created [ID={new_id}]:")
    print(f"  Email    : {EMAIL}")
    print(f"  Password : {PASSWORD}")
    print("  Role     : admin")
