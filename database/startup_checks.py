"""
Database startup validation — checks required tables and creates missing config.
Called once during app factory initialization.
"""

import logging
from database.connection import execute_query, get_db_cursor

logger = logging.getLogger(__name__)

REQUIRED_TABLES = ['users', 'admins', 'managers', 'employees', 'tasks', 'delays', 'activity_logs', 'search_logs', 'feedback', 'resources']


def validate_schema() -> dict:
    """
    Check that required tables/views exist in the database.
    """
    result = {"ok": True, "missing": [], "checked": []}

    try:
        rows = execute_query(
            """
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
            """,
            fetch=True,
        )
        existing = {row['table_name'] for row in rows}

        for table in REQUIRED_TABLES:
            if table in existing:
                result["checked"].append(table)
            else:
                result["missing"].append(table)
                result["ok"] = False

        if result["ok"]:
            logger.info("DB schema validation passed — all %d required tables/views present", len(REQUIRED_TABLES))
        else:
            logger.warning("DB schema validation: missing tables %s", result["missing"])

    except Exception as e:
        logger.error("DB schema validation failed: %s", e)
        result["ok"] = False
        result["error"] = str(e)

    return result


def ensure_elite_tables() -> None:
    """Create advanced intelligence tables if they don't exist."""
    try:
        with get_db_cursor() as cursor:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS risk_history (
                    id          SERIAL PRIMARY KEY,
                    user_id     INTEGER NOT NULL,
                    risk_score  REAL NOT NULL,
                    recorded_at TIMESTAMP DEFAULT NOW()
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS ai_snapshots (
                    id           SERIAL PRIMARY KEY,
                    user_id      INTEGER NOT NULL,
                    role         VARCHAR(20),
                    summary_json JSONB,
                    created_at   TIMESTAMP DEFAULT NOW()
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS system_health_snapshots (
                    id             SERIAL PRIMARY KEY,
                    snapshot_json  JSONB,
                    created_at     TIMESTAMP DEFAULT NOW()
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS user_analytics_summary (
                    user_id             INTEGER PRIMARY KEY,
                    avg_authenticity    REAL DEFAULT 0,
                    avg_avoidance       REAL DEFAULT 0,
                    delay_count_total   INTEGER DEFAULT 0,
                    updated_at          TIMESTAMP DEFAULT NOW()
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS admin_login (
                    user_id       INTEGER PRIMARY KEY,
                    email         VARCHAR(255) UNIQUE NOT NULL,
                    password_hash VARCHAR(255) NOT NULL
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS manager_login (
                    user_id       INTEGER PRIMARY KEY,
                    email         VARCHAR(255) UNIQUE NOT NULL,
                    password_hash VARCHAR(255) NOT NULL
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS employee_login (
                    user_id       INTEGER PRIMARY KEY,
                    email         VARCHAR(255) UNIQUE NOT NULL,
                    password_hash VARCHAR(255) NOT NULL
                )
            """)
        logger.info("Elite intelligence tables verified/created")
    except Exception as e:
        logger.warning("Could not ensure elite tables: %s", e)


def ensure_system_config() -> None:
    """
    Create the system_config table with sensible defaults if it doesn't exist.
    This prevents analytics from crashing on _fetch_neural_sensitivity().
    """
    try:
        with get_db_cursor() as cursor:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS system_config (
                    id          INTEGER PRIMARY KEY DEFAULT 1,
                    neural_sensitivity  REAL    DEFAULT 8.5,
                    ai_confidence       INTEGER DEFAULT 10,
                    detection_window    INTEGER DEFAULT 14,
                    risk_threshold      INTEGER DEFAULT 3,
                    max_load_time       INTEGER DEFAULT 200,
                    backup_freq         VARCHAR(32) DEFAULT 'EVERY 6H',
                    updated_at          TIMESTAMP DEFAULT NOW()
                )
            """)
            # Insert default row if table was just created (empty)
            cursor.execute("""
                INSERT INTO system_config (id)
                SELECT 1
                WHERE NOT EXISTS (SELECT 1 FROM system_config WHERE id = 1)
            """)
        logger.info("system_config table verified/created")
    except Exception as e:
        logger.warning("Could not ensure system_config table: %s", e)


def ensure_optional_tables() -> None:
    """Create optional tables that routes depend on, if they don't exist."""
    try:
        with get_db_cursor() as cursor:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS search_logs (
                    id         SERIAL PRIMARY KEY,
                    user_id    INTEGER,
                    query      TEXT NOT NULL,
                    timestamp  TIMESTAMP DEFAULT NOW()
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS feedback (
                    id         SERIAL PRIMARY KEY,
                    user_id    INTEGER,
                    rating     INTEGER NOT NULL CHECK (rating BETWEEN 1 AND 5),
                    comment    TEXT DEFAULT '',
                    created_at TIMESTAMP DEFAULT NOW()
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS activity_logs (
                    id          SERIAL PRIMARY KEY,
                    user_id     INTEGER REFERENCES users(id) ON DELETE SET NULL,
                    action      VARCHAR(255) NOT NULL,
                    details     TEXT,
                    ip_address  VARCHAR(45),
                    created_at  TIMESTAMP DEFAULT NOW()
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS resources (
                    id             SERIAL PRIMARY KEY,
                    title          VARCHAR(255) NOT NULL,
                    description    TEXT,
                    url            VARCHAR(500),
                    resource_type  VARCHAR(50),
                    is_active      BOOLEAN DEFAULT TRUE,
                    created_at     TIMESTAMP DEFAULT NOW(),
                    updated_at     TIMESTAMP DEFAULT NOW()
                )
            """)
        logger.info("Optional tables (search_logs, feedback, activity_logs, resources) verified/created")
    except Exception as e:
        logger.warning("Could not ensure optional tables: %s", e)


def ensure_user_columns() -> None:
    """Add missing columns to the physical role tables for advanced analytics."""
    try:
        with get_db_cursor() as cursor:
            for tbl in ['admins', 'managers', 'employees']:
                cursor.execute(f"""
                    ALTER TABLE {tbl} ADD COLUMN IF NOT EXISTS reliability_score REAL DEFAULT 100.0;
                    ALTER TABLE {tbl} ADD COLUMN IF NOT EXISTS last_active_at   TIMESTAMP DEFAULT NOW();
                    ALTER TABLE {tbl} ADD COLUMN IF NOT EXISTS job_role         VARCHAR(255);
                    ALTER TABLE {tbl} ADD COLUMN IF NOT EXISTS neural_notifications BOOLEAN DEFAULT TRUE;
                    ALTER TABLE {tbl} ADD COLUMN IF NOT EXISTS neural_auto_analysis BOOLEAN DEFAULT TRUE;
                    ALTER TABLE {tbl} ADD COLUMN IF NOT EXISTS neural_temperature   FLOAT DEFAULT 0.7;
                """)
        logger.info("Physical role table columns (reliability, activity, job_role, neural_config) verified/added")
    except Exception as e:
        logger.warning("Could not add columns to physical role tables: %s", e)


def ensure_database_indexes() -> None:
    """Create indexes for faster analytics queries."""
    try:
        with get_db_cursor() as cursor:
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_delays_user_submitted ON delays(user_id, submitted_at DESC)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_tasks_user_status ON tasks(assigned_to, status)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_delays_risk_level ON delays(risk_level)")
        logger.info("Database indexes for analytics performance verified/created")
    except Exception as e:
        logger.warning("Could not ensure database indexes: %s", e)


def run_startup_checks() -> dict:
    """Run all startup DB checks. Returns schema validation result."""
    from database.setup_role_tables import ensure_role_tables
    ensure_role_tables()
    ensure_user_columns()
    ensure_system_config()
    ensure_optional_tables()
    ensure_elite_tables()
    ensure_database_indexes()
    return validate_schema()

