-- Migration: Add missing Elite Intelligence columns to delays table
ALTER TABLE delays ADD COLUMN IF NOT EXISTS verdict TEXT;
ALTER TABLE delays ADD COLUMN IF NOT EXISTS confidence_score INTEGER DEFAULT 0;
ALTER TABLE delays ADD COLUMN IF NOT EXISTS feature_vector JSONB;
ALTER TABLE delays ADD COLUMN IF NOT EXISTS governance_snapshot JSONB;
ALTER TABLE delays ADD COLUMN IF NOT EXISTS risk_pattern TEXT;

-- Migration: Add search_logs table
CREATE TABLE IF NOT EXISTS search_logs (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    query TEXT NOT NULL,
    results_count INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
