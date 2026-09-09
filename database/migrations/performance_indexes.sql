-- Production Performance Optimization
-- Governance Level D+: Quant-Grade Indexing

-- Optimize user-level risk lookups for analytics and contagion detection
CREATE INDEX IF NOT EXISTS idx_risk_history_user_ts 
ON risk_history(user_id, recorded_at DESC);

-- Optimize recent system-wide risk trends
CREATE INDEX IF NOT EXISTS idx_risk_history_ts
ON risk_history(recorded_at DESC);

-- Optimize analytics lookups
CREATE INDEX IF NOT EXISTS idx_tasks_assigned_status
ON tasks(assigned_to, status);
