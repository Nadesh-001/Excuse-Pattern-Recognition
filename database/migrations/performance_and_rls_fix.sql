-- =============================================================================
-- Migration: Performance Indexes + Disable RLS
-- Run once in Supabase SQL Editor
-- =============================================================================

-- ---------------------------------------------------------------------------
-- 1. Missing indexes on runtime-created tables (activity_logs, search_logs)
--    These tables are created by startup_checks.py without indexes.
-- ---------------------------------------------------------------------------

CREATE INDEX IF NOT EXISTS idx_activity_logs_user_id  ON activity_logs(user_id);
CREATE INDEX IF NOT EXISTS idx_activity_logs_action    ON activity_logs(action);
CREATE INDEX IF NOT EXISTS idx_activity_logs_created   ON activity_logs(created_at DESC);

CREATE INDEX IF NOT EXISTS idx_search_logs_user_id     ON search_logs(user_id);

-- ---------------------------------------------------------------------------
-- 2. Composite indexes for analytics queries (high-impact)
-- ---------------------------------------------------------------------------

-- Most analytics queries filter by user_id AND sort by submitted_at
-- Already exists: idx_delays_user_submitted ON delays(user_id, submitted_at DESC)
-- Add task-level composite:
CREATE INDEX IF NOT EXISTS idx_delays_user_task         ON delays(user_id, task_id);

-- Composite for task list queries (role-based filters)
-- Already exists: idx_tasks_user_status ON tasks(assigned_to, status)

-- ---------------------------------------------------------------------------
-- 3. Partial index for high-risk delays (analytics hot path)
-- ---------------------------------------------------------------------------

CREATE INDEX IF NOT EXISTS idx_delays_high_risk
    ON delays(user_id, submitted_at DESC)
    WHERE risk_level = 'High';

-- ---------------------------------------------------------------------------
-- 4. Disable RLS — Flask handles all auth via session + role checks.
--    RLS with no policies blocks all rows for non-superuser connections.
-- ---------------------------------------------------------------------------

ALTER TABLE users       DISABLE ROW LEVEL SECURITY;
ALTER TABLE tasks       DISABLE ROW LEVEL SECURITY;
ALTER TABLE delays      DISABLE ROW LEVEL SECURITY;
ALTER TABLE attachments DISABLE ROW LEVEL SECURITY;
ALTER TABLE audit_logs  DISABLE ROW LEVEL SECURITY;

-- Drop any existing (likely empty/restrictive) policies to keep it clean
DO $$
DECLARE
    r RECORD;
BEGIN
    FOR r IN
        SELECT policyname, tablename
        FROM pg_policies
        WHERE schemaname = 'public'
    LOOP
        EXECUTE format('DROP POLICY IF EXISTS %I ON %I', r.policyname, r.tablename);
    END LOOP;
END
$$;
