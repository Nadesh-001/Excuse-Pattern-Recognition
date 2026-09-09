"""
AWS RDS PostgreSQL Setup Script
Applies rds_schema.sql to the configured AWS RDS instance.

Usage:
    python database/setup_rds.py

Environment variables required (from .env):
    DB_HOST, DB_PORT, DB_USER, DB_PASSWORD, DB_NAME
"""

import os
import sys
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

# Load .env from project root
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

SCHEMA_FILE = os.path.join(os.path.dirname(__file__), 'rds_schema.sql')


def get_connection():
    """Create a direct psycopg2 connection to AWS RDS."""
    return psycopg2.connect(
        host=os.getenv("DB_HOST"),
        port=int(os.getenv("DB_PORT", "5432")),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        database=os.getenv("DB_NAME"),
        sslmode="require",
        connect_timeout=10,
    )


def run_setup():
    """Apply rds_schema.sql to the AWS RDS database."""
    print("=" * 60)
    print("  AWS RDS — Neural_Protocol Schema Setup")
    print("=" * 60)

    # Validate env vars
    required = ["DB_HOST", "DB_PORT", "DB_USER", "DB_PASSWORD", "DB_NAME"]
    missing = [k for k in required if not os.getenv(k)]
    if missing:
        print(f"  [ERROR] Missing environment variables: {', '.join(missing)}")
        print("  Please check your .env file.")
        sys.exit(1)

    print(f"  Host     : {os.getenv('DB_HOST')}")
    print(f"  Port     : {os.getenv('DB_PORT')}")
    print(f"  Database : {os.getenv('DB_NAME')}")
    print(f"  User     : {os.getenv('DB_USER')}")
    print()

    # Read schema file
    if not os.path.exists(SCHEMA_FILE):
        print(f"  [ERROR] Schema file not found: {SCHEMA_FILE}")
        sys.exit(1)

    with open(SCHEMA_FILE, 'r', encoding='utf-8') as f:
        schema_sql = f.read()

    # Connect and apply schema
    conn = None
    try:
        print("  Connecting to AWS RDS ...", end=" ", flush=True)
        conn = get_connection()
        print("OK")

        print("  Applying schema ...", end=" ", flush=True)
        with conn.cursor() as cur:
            cur.execute(schema_sql)
        conn.commit()
        print("OK")

        # Verify tables
        print()
        print("  Verifying tables ...")
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
                ORDER BY table_name
            """)
            tables = [row['table_name'] for row in cur.fetchall()]

        for t in tables:
            print(f"    [OK] {t}")

        print()
        print(f"  {len(tables)} tables verified.")
        print()
        print("  Schema setup completed successfully!")
        print("=" * 60)

    except psycopg2.OperationalError as e:
        print(f"FAILED\n  [ERROR] Cannot connect to RDS: {e}")
        print("\n  Checklist:")
        print("  1. RDS instance is running and publicly accessible")
        print("  2. Security Group allows inbound on port 5432")
        print("  3. DB_HOST, DB_USER, DB_PASSWORD, DB_NAME are correct in .env")
        sys.exit(1)

    except Exception as e:
        if conn:
            conn.rollback()
        print(f"\n  [ERROR] Schema setup failed: {e}")
        sys.exit(1)

    finally:
        if conn:
            conn.close()


if __name__ == "__main__":
    run_setup()
