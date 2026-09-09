"""
Seed Manager and Employee users in the database.
"""
import sys
sys.path.insert(0, '.')

from database.connection import get_db_cursor
import bcrypt

USERS_TO_SEED = [
    {
        "email": "manager@excuseai.com",
        "password": "Manager@2026",
        "name": "Manager",
        "role": "manager"
    },
    {
        "email": "employee@excuseai.com",
        "password": "Employee@2026",
        "name": "Employee",
        "role": "employee"
    }
]

def seed():
    with get_db_cursor() as cur:
        for u in USERS_TO_SEED:
            # Check if user already exists
            cur.execute("SELECT id FROM users WHERE email = %s", (u["email"],))
            res = cur.fetchone()
            if res:
                print(f"User {u['email']} already exists [ID={res['id']}].")
                continue
            
            # Hash password
            hashed = bcrypt.hashpw(u["password"].encode(), bcrypt.gensalt(12)).decode()
            
            # Insert user
            cur.execute(
                """
                INSERT INTO users (full_name, email, password_hash, role, active_status)
                VALUES (%s, %s, %s, %s, TRUE)
                RETURNING id
                """,
                (u["name"], u["email"], hashed, u["role"])
            )
            new_id = cur.fetchone()['id']
            print(f"Created {u['role']} user [ID={new_id}] with email {u['email']}.")

if __name__ == "__main__":
    seed()
