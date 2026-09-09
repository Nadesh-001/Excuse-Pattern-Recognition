"""
Role Table Splitter & Migration Service (Option 1 Architecture)
Splits user records into 3 dedicated physical tables: 'admins', 'managers', and 'employees'
with a central PostgreSQL sequence ('user_id_seq') and a unified 'users' SQL View.
"""

import logging
from database.connection import execute_query, get_db_cursor

logger = logging.getLogger(__name__)

ROLE_TABLES = {
    'admin':           'admins',
    'main_admin':      'admins',
    'secondary_admin': 'admins',
    'manager':         'managers',
    'employee':        'employees',
}

def ensure_role_tables() -> None:
    """
    Creates admins, managers, employees physical tables,
    user_id_seq sequence, migrates existing data from base users table,
    and replaces 'users' table with a unified SQL View.
    """
    try:
        with get_db_cursor() as cursor:
            # 1. Create central sequence for unique IDs across all roles
            cursor.execute("CREATE SEQUENCE IF NOT EXISTS user_id_seq START WITH 1;")

            # 2. Create physical role tables
            for role_name, table_name in ROLE_TABLES.items():
                cursor.execute(f"""
                    CREATE TABLE IF NOT EXISTS {table_name} (
                        id                      INTEGER PRIMARY KEY DEFAULT nextval('user_id_seq'),
                        full_name               VARCHAR(255)    NOT NULL,
                        email                   VARCHAR(255)    UNIQUE NOT NULL,
                        password_hash           VARCHAR(255)    NOT NULL,
                        role                    VARCHAR(20)     DEFAULT '{role_name}',
                        active_status           BOOLEAN         DEFAULT TRUE,
                        created_at              TIMESTAMP       DEFAULT CURRENT_TIMESTAMP,
                        job_role                VARCHAR(255),
                        avatar_url              TEXT,
                        bio                     TEXT,
                        phone                   VARCHAR(50),
                        city                    VARCHAR(100),
                        country                 VARCHAR(100),
                        postal_code             VARCHAR(20),
                        last_active_at          TIMESTAMP       DEFAULT CURRENT_TIMESTAMP,
                        reliability_score       FLOAT           DEFAULT 100.0,
                        neural_notifications    BOOLEAN         DEFAULT TRUE,
                        neural_auto_analysis    BOOLEAN         DEFAULT TRUE,
                        neural_temperature      FLOAT           DEFAULT 0.7
                    );
                """)
                cursor.execute(f"CREATE INDEX IF NOT EXISTS idx_{table_name}_email ON {table_name}(email);")

            # Drop legacy constraints on login helper tables if present
            for l_table in ['admin_login', 'manager_login', 'employee_login']:
                cursor.execute(f"ALTER TABLE IF EXISTS {l_table} DROP CONSTRAINT IF EXISTS {l_table}_user_id_fkey;")

            # 3. Check if 'users' is currently a BASE TABLE (legacy single table)
            cursor.execute("""
                SELECT table_type 
                FROM information_schema.tables 
                WHERE table_schema = 'public' AND table_name = 'users';
            """)
            table_info = cursor.fetchone()

            if table_info and table_info['table_type'] == 'BASE TABLE':
                logger.info("Migrating base 'users' table into physical role tables (admins, managers, employees)...")

                # Copy rows into role tables if not already present
                cursor.execute("""
                    INSERT INTO admins (id, full_name, email, password_hash, role, active_status, created_at, job_role, avatar_url, bio, phone, city, country, postal_code, last_active_at, reliability_score, neural_notifications, neural_auto_analysis, neural_temperature)
                    SELECT id, full_name, email, password_hash, 'admin', active_status, created_at, job_role, avatar_url, bio, phone, city, country, postal_code, last_active_at, COALESCE(reliability_score, 100.0), COALESCE(neural_notifications, TRUE), COALESCE(neural_auto_analysis, TRUE), COALESCE(neural_temperature, 0.7)
                    FROM users WHERE LOWER(role) = 'admin'
                    ON CONFLICT (email) DO NOTHING;
                """)

                cursor.execute("""
                    INSERT INTO managers (id, full_name, email, password_hash, role, active_status, created_at, job_role, avatar_url, bio, phone, city, country, postal_code, last_active_at, reliability_score, neural_notifications, neural_auto_analysis, neural_temperature)
                    SELECT id, full_name, email, password_hash, 'manager', active_status, created_at, job_role, avatar_url, bio, phone, city, country, postal_code, last_active_at, COALESCE(reliability_score, 100.0), COALESCE(neural_notifications, TRUE), COALESCE(neural_auto_analysis, TRUE), COALESCE(neural_temperature, 0.7)
                    FROM users WHERE LOWER(role) = 'manager'
                    ON CONFLICT (email) DO NOTHING;
                """)

                cursor.execute("""
                    INSERT INTO employees (id, full_name, email, password_hash, role, active_status, created_at, job_role, avatar_url, bio, phone, city, country, postal_code, last_active_at, reliability_score, neural_notifications, neural_auto_analysis, neural_temperature)
                    SELECT id, full_name, email, password_hash, 'employee', active_status, created_at, job_role, avatar_url, bio, phone, city, country, postal_code, last_active_at, COALESCE(reliability_score, 100.0), COALESCE(neural_notifications, TRUE), COALESCE(neural_auto_analysis, TRUE), COALESCE(neural_temperature, 0.7)
                    FROM users WHERE LOWER(role) NOT IN ('admin', 'manager') OR role IS NULL
                    ON CONFLICT (email) DO NOTHING;
                """)

                # Rename old base users table to users_legacy
                cursor.execute("ALTER TABLE users RENAME TO users_legacy;")
                logger.info("Renamed legacy 'users' table to 'users_legacy'.")

            # 4. Widen role column constraint on admins table to accept new sub-roles
            cursor.execute("""
                ALTER TABLE admins DROP CONSTRAINT IF EXISTS admins_role_check;
            """)
            cursor.execute("""
                ALTER TABLE admins ADD CONSTRAINT admins_role_check
                    CHECK (role IN ('admin', 'main_admin', 'secondary_admin'));
            """)

            # 4b. Create/Replace unified 'users' SQL View — uses real role column
            #     so main_admin / secondary_admin are visible to the application.
            cursor.execute("""
                CREATE OR REPLACE VIEW users AS
                SELECT id, full_name, email, password_hash, role, active_status, created_at, job_role, avatar_url, bio, phone, city, country, postal_code, last_active_at, reliability_score, neural_notifications, neural_auto_analysis, neural_temperature FROM admins
                UNION ALL
                SELECT id, full_name, email, password_hash, role, active_status, created_at, job_role, avatar_url, bio, phone, city, country, postal_code, last_active_at, reliability_score, neural_notifications, neural_auto_analysis, neural_temperature FROM managers
                UNION ALL
                SELECT id, full_name, email, password_hash, role, active_status, created_at, job_role, avatar_url, bio, phone, city, country, postal_code, last_active_at, reliability_score, neural_notifications, neural_auto_analysis, neural_temperature FROM employees;
            """)

            # 4c. Partial unique index: only one active main_admin may exist at a time.
            #     Enforced at DB level to prevent race conditions.
            cursor.execute("""
                CREATE UNIQUE INDEX IF NOT EXISTS one_active_main_admin
                ON admins (role)
                WHERE role = 'main_admin' AND active_status = TRUE;
            """)

            # 5. Synchronize sequence user_id_seq to max ID
            cursor.execute("""
                SELECT setval('user_id_seq', GREATEST(
                    COALESCE((SELECT MAX(id) FROM admins), 0),
                    COALESCE((SELECT MAX(id) FROM managers), 0),
                    COALESCE((SELECT MAX(id) FROM employees), 0)
                ) + 1, false);
            """)

            # 5b. Migrate any legacy 'admin' rows to 'main_admin' (first one) and
            #     'secondary_admin' (all others). Idempotent — only acts on 'admin' rows.
            cursor.execute("""
                DO $$
                DECLARE first_admin_id INTEGER;
                BEGIN
                    -- Find the lowest-ID active admin (the primary account)
                    SELECT id INTO first_admin_id
                    FROM admins
                    WHERE role = 'admin' AND active_status = TRUE
                    ORDER BY id ASC
                    LIMIT 1;

                    IF first_admin_id IS NOT NULL THEN
                        -- Promote the primary admin
                        UPDATE admins SET role = 'main_admin' WHERE id = first_admin_id;
                        -- Demote remaining legacy admins to secondary_admin
                        UPDATE admins SET role = 'secondary_admin'
                        WHERE role = 'admin' AND id != first_admin_id;
                    END IF;
                END;
                $$;
            """)

            # 6. Seed default accounts in physical tables if missing
            default_accounts = [
                ('admins', 'Admin', 'admin@excuseai.com', '$2b$12$dPOA4TcWsh/xO57KXWDPuuyyAjJbHtDJOJuh6scEkz9eOYGbS1Him', 'main_admin'),
                ('managers', 'Manager', 'manager@excuseai.com', '$2b$12$dPOA4TcWsh/xO57KXWDPuuyyAjJbHtDJOJuh6scEkz9eOYGbS1Him', 'manager'),
                ('employees', 'Employee', 'employee@excuseai.com', '$2b$12$dPOA4TcWsh/xO57KXWDPuuyyAjJbHtDJOJuh6scEkz9eOYGbS1Him', 'employee')
            ]
            for target_table, name, email, pass_hash, role in default_accounts:
                cursor.execute(f"""
                    INSERT INTO {target_table} (full_name, email, password_hash, role, active_status)
                    VALUES (%s, %s, %s, %s, TRUE)
                    ON CONFLICT (email) DO NOTHING;
                """, (name, email, pass_hash, role))

        logger.info("Successfully setup role physical tables (admins, managers, employees) and unified 'users' view.")
    except Exception as e:
        logger.error("Failed to setup role tables: %s", e)

