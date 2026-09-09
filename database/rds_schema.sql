-- ============================================================
-- AWS RDS PostgreSQL Schema
-- Task Management System with AI-powered Delay Analysis
-- Neural_Protocol Application
-- ============================================================

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ============================================================
-- USERS TABLE
-- ============================================================
CREATE TABLE IF NOT EXISTS users (
    id                      SERIAL PRIMARY KEY,
    full_name               VARCHAR(255)    NOT NULL,
    email                   VARCHAR(255)    UNIQUE NOT NULL,
    password_hash           VARCHAR(255)    NOT NULL,
    role                    VARCHAR(20)     CHECK (role IN ('employee', 'manager', 'admin')) DEFAULT 'employee',
    active_status           BOOLEAN         DEFAULT TRUE,
    created_at              TIMESTAMP       DEFAULT CURRENT_TIMESTAMP,
    job_role                VARCHAR(255),
    avatar_url              TEXT,
    bio                     TEXT,
    phone                   VARCHAR(50),
    city                    VARCHAR(100),
    country                 VARCHAR(100),
    postal_code             VARCHAR(20),
    last_active_at          TIMESTAMP,
    reliability_score       FLOAT           DEFAULT 100.0,
    neural_notifications    BOOLEAN         DEFAULT TRUE,
    neural_auto_analysis    BOOLEAN         DEFAULT TRUE,
    neural_temperature      FLOAT           DEFAULT 0.7
);

CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
CREATE INDEX IF NOT EXISTS idx_users_role  ON users(role);

-- ============================================================
-- TASKS TABLE
-- ============================================================
CREATE TABLE IF NOT EXISTS tasks (
    id                      SERIAL PRIMARY KEY,
    title                   VARCHAR(255)    NOT NULL,
    description             TEXT,
    assigned_to             INTEGER         REFERENCES users(id) ON DELETE SET NULL,
    created_by              INTEGER         REFERENCES users(id) ON DELETE SET NULL,
    status                  VARCHAR(50)     DEFAULT 'Pending',
    priority                VARCHAR(50)     DEFAULT 'Medium',
    deadline                DATE,
    estimated_minutes       INTEGER         DEFAULT 0,
    created_at              TIMESTAMP       DEFAULT CURRENT_TIMESTAMP,
    completion_timestamp    TIMESTAMP       NULL,
    complexity              INTEGER         DEFAULT 1,
    predicted_risk          INTEGER         DEFAULT 0,
    risk_factors            JSONB           DEFAULT '{}',
    category                VARCHAR(100)    DEFAULT 'General',
    CONSTRAINT chk_status   CHECK (status IN ('Pending', 'In Progress', 'Completed', 'Delayed')),
    CONSTRAINT chk_priority CHECK (priority IN ('Low', 'Medium', 'High'))
);

CREATE INDEX IF NOT EXISTS idx_tasks_assigned_to ON tasks(assigned_to);
CREATE INDEX IF NOT EXISTS idx_tasks_created_by  ON tasks(created_by);
CREATE INDEX IF NOT EXISTS idx_tasks_status      ON tasks(status);
CREATE INDEX IF NOT EXISTS idx_tasks_deadline    ON tasks(deadline);

-- ============================================================
-- DELAYS TABLE
-- ============================================================
CREATE TABLE IF NOT EXISTS delays (
    id                  SERIAL PRIMARY KEY,
    task_id             INTEGER     REFERENCES tasks(id) ON DELETE CASCADE,
    user_id             INTEGER     REFERENCES users(id) ON DELETE SET NULL,
    reason_text         TEXT,
    reason_audio_path   TEXT,
    score_authenticity  INTEGER     CHECK (score_authenticity BETWEEN 0 AND 100),
    score_avoidance     INTEGER     CHECK (score_avoidance BETWEEN 0 AND 100),
    risk_level          VARCHAR(50) CHECK (risk_level IN ('Low', 'Medium', 'High')),
    ai_feedback         TEXT,
    ai_analysis_json    JSONB,
    delay_duration      INTEGER     DEFAULT 0,
    proof_path          TEXT,
    submitted_at        TIMESTAMP   DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_delays_task_id    ON delays(task_id);
CREATE INDEX IF NOT EXISTS idx_delays_user_id    ON delays(user_id);
CREATE INDEX IF NOT EXISTS idx_delays_risk_level ON delays(risk_level);

-- ============================================================
-- ATTACHMENTS TABLE
-- ============================================================
CREATE TABLE IF NOT EXISTS attachments (
    id                  SERIAL PRIMARY KEY,
    task_id             INTEGER     REFERENCES tasks(id) ON DELETE CASCADE,
    resource_type       VARCHAR(50),
    url_or_path         TEXT,
    title               VARCHAR(255),
    ai_summary          TEXT,
    requirements_json   JSONB,
    deadlines_json      JSONB,
    completeness_score  INTEGER,
    uploaded_at         TIMESTAMP   DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_attachments_task_id ON attachments(task_id);

-- ============================================================
-- ACTIVITY LOGS TABLE
-- ============================================================
CREATE TABLE IF NOT EXISTS activity_logs (
    id          SERIAL PRIMARY KEY,
    user_id     INTEGER     REFERENCES users(id) ON DELETE SET NULL,
    action      VARCHAR(255) NOT NULL,
    details     TEXT,
    ip_address  VARCHAR(45),
    created_at  TIMESTAMP   DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_activity_logs_user_id    ON activity_logs(user_id);
CREATE INDEX IF NOT EXISTS idx_activity_logs_created_at ON activity_logs(created_at);

-- ============================================================
-- AUDIT LOGS TABLE
-- ============================================================
CREATE TABLE IF NOT EXISTS audit_logs (
    id          SERIAL PRIMARY KEY,
    user_id     INTEGER     REFERENCES users(id) ON DELETE SET NULL,
    action      VARCHAR(255),
    details     TEXT,
    timestamp   TIMESTAMP   DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_audit_logs_user_id   ON audit_logs(user_id);
CREATE INDEX IF NOT EXISTS idx_audit_logs_timestamp ON audit_logs(timestamp);
CREATE INDEX IF NOT EXISTS idx_audit_logs_action    ON audit_logs(action);

-- ============================================================
-- RESOURCE LOGS TABLE
-- ============================================================
CREATE TABLE IF NOT EXISTS resource_logs (
    id              SERIAL PRIMARY KEY,
    user_id         INTEGER     REFERENCES users(id) ON DELETE SET NULL,
    attachment_id   INTEGER     REFERENCES attachments(id) ON DELETE CASCADE,
    accessed_at     TIMESTAMP   DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_resource_logs_user_id       ON resource_logs(user_id);
CREATE INDEX IF NOT EXISTS idx_resource_logs_attachment_id ON resource_logs(attachment_id);

-- ============================================================
-- RESOURCES TABLE (External links / training material)
-- ============================================================
CREATE TABLE IF NOT EXISTS resources (
    id              SERIAL PRIMARY KEY,
    title           VARCHAR(255) NOT NULL,
    description     TEXT,
    url             VARCHAR(500),
    resource_type   VARCHAR(50),
    is_active       BOOLEAN     DEFAULT TRUE,
    created_at      TIMESTAMP   DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP   DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================
-- FEEDBACK TABLE
-- ============================================================
CREATE TABLE IF NOT EXISTS feedback (
    id          SERIAL PRIMARY KEY,
    user_id     INTEGER     REFERENCES users(id) ON DELETE SET NULL,
    rating      INTEGER     CHECK (rating BETWEEN 1 AND 5),
    comment     TEXT        DEFAULT '',
    created_at  TIMESTAMP   DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_feedback_user_id ON feedback(user_id);
CREATE INDEX IF NOT EXISTS idx_feedback_rating  ON feedback(rating);

-- ============================================================
-- RISK HISTORY TABLE
-- ============================================================
CREATE TABLE IF NOT EXISTS risk_history (
    id          SERIAL PRIMARY KEY,
    user_id     INTEGER     REFERENCES users(id) ON DELETE CASCADE,
    task_id     INTEGER     REFERENCES tasks(id) ON DELETE CASCADE,
    risk_score  REAL        NOT NULL,
    recorded_at TIMESTAMP   DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_risk_history_user_id ON risk_history(user_id);
CREATE INDEX IF NOT EXISTS idx_risk_history_task_id ON risk_history(task_id);

-- ============================================================
-- SYSTEM CONFIG TABLE
-- ============================================================
CREATE TABLE IF NOT EXISTS system_config (
    id                  INTEGER     PRIMARY KEY DEFAULT 1,
    neural_sensitivity  REAL        DEFAULT 8.5,
    ai_confidence       INTEGER     DEFAULT 10,
    detection_window    INTEGER     DEFAULT 14,
    risk_threshold      INTEGER     DEFAULT 3,
    max_load_time       INTEGER     DEFAULT 200,
    backup_freq         VARCHAR(32) DEFAULT 'EVERY 6H',
    ai_enabled          BOOLEAN     DEFAULT TRUE,
    updated_at          TIMESTAMP   DEFAULT CURRENT_TIMESTAMP
);

-- Insert default config row
INSERT INTO system_config (id, neural_sensitivity, ai_enabled)
VALUES (1, 8.5, TRUE)
ON CONFLICT (id) DO NOTHING;

-- ============================================================
-- AI SNAPSHOTS TABLE
-- ============================================================
CREATE TABLE IF NOT EXISTS ai_snapshots (
    id              SERIAL PRIMARY KEY,
    user_id         INTEGER     REFERENCES users(id) ON DELETE CASCADE,
    role            VARCHAR(20),
    summary_json    JSONB,
    created_at      TIMESTAMP   DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_ai_snapshots_user_role ON ai_snapshots(user_id, role);

-- ============================================================
-- SYSTEM HEALTH SNAPSHOTS TABLE
-- ============================================================
CREATE TABLE IF NOT EXISTS system_health_snapshots (
    id              SERIAL PRIMARY KEY,
    snapshot_json   JSONB,
    created_at      TIMESTAMP   DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================
-- SEARCH LOGS TABLE
-- ============================================================
CREATE TABLE IF NOT EXISTS search_logs (
    id          SERIAL PRIMARY KEY,
    user_id     INTEGER     REFERENCES users(id) ON DELETE SET NULL,
    query       TEXT        NOT NULL,
    timestamp   TIMESTAMP   DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_search_logs_user_id    ON search_logs(user_id);
CREATE INDEX IF NOT EXISTS idx_search_logs_timestamp  ON search_logs(timestamp);

-- ============================================================
-- USER ANALYTICS SUMMARY TABLE (Welford's algorithm)
-- ============================================================
CREATE TABLE IF NOT EXISTS user_analytics_summary (
    user_id             INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    avg_authenticity    FLOAT   DEFAULT 0.0,
    std_authenticity    FLOAT   DEFAULT 0.0,
    auth_M2             FLOAT   DEFAULT 0.0,
    avg_avoidance       FLOAT   DEFAULT 0.0,
    std_avoidance       FLOAT   DEFAULT 0.0,
    avoid_M2            FLOAT   DEFAULT 0.0,
    delay_count_total   INTEGER DEFAULT 0,
    last_updated        TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_user_analytics_user_id ON user_analytics_summary(user_id);

-- ============================================================
-- VIEWS
-- ============================================================
CREATE OR REPLACE VIEW task_statistics AS
SELECT
    u.id            AS user_id,
    u.full_name,
    u.email,
    u.role,
    COUNT(t.id)     AS total_tasks,
    COUNT(CASE WHEN t.status = 'Completed'  THEN 1 END) AS completed_tasks,
    COUNT(CASE WHEN t.status = 'Delayed'    THEN 1 END) AS delayed_tasks,
    COUNT(CASE WHEN t.status = 'Pending'    THEN 1 END) AS pending_tasks,
    COUNT(d.id)     AS total_delays,
    AVG(d.score_authenticity) AS avg_authenticity_score
FROM users u
LEFT JOIN tasks  t ON t.assigned_to = u.id
LEFT JOIN delays d ON d.user_id     = u.id
GROUP BY u.id, u.full_name, u.email, u.role;

-- ============================================================
-- DEFAULT ADMIN USER
-- Password: Admin@2026  (bcrypt hash)
-- ============================================================
INSERT INTO users (full_name, email, password_hash, role, active_status)
VALUES (
    'Admin',
    'admin@excuseai.com',
    '$2b$12$dPOA4TcWsh/xO57KXWDPuuyyAjJbHtDJOJuh6scEkz9eOYGbS1Him',
    'admin',
    TRUE
)
ON CONFLICT (email) DO NOTHING;
