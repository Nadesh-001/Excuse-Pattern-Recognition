-- Database Optimization: Indices and Materialized View Structure

-- 1. Create Indexes for faster Analytics Joins
CREATE INDEX IF NOT EXISTS idx_delays_user_submitted ON delays(user_id, submitted_at DESC);
CREATE INDEX IF NOT EXISTS idx_tasks_user_status ON tasks(assigned_to, status);
CREATE INDEX IF NOT EXISTS idx_delays_risk_level ON delays(risk_level);

-- 2. Create User Analytics Summary Table (Snapshot Table)
CREATE TABLE IF NOT EXISTS user_analytics_summary (
    user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    total_tasks INTEGER DEFAULT 0,
    total_delays INTEGER DEFAULT 0,
    unique_delayed_tasks INTEGER DEFAULT 0,
    avg_authenticity FLOAT DEFAULT 0,
    avg_avoidance FLOAT DEFAULT 0,
    risk_low_count INTEGER DEFAULT 0,
    risk_med_count INTEGER DEFAULT 0,
    risk_high_count INTEGER DEFAULT 0,
    wrs_score FLOAT DEFAULT 0,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 3. Function/Query logic (to be used in application code)
/* 
   We will not create a Stored Procedure as it depends on PL/pgSQL availability 
   and specific permission sets. We will execute the following Logic 
   via Python to refresh the summary.
*/
