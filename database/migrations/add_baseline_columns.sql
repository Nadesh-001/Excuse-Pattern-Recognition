-- Migration: Add Welford baseline columns to user_analytics_summary
-- Run once in Supabase SQL Editor
-- Safe: uses IF NOT EXISTS / IF column does not exist

ALTER TABLE user_analytics_summary
  ADD COLUMN IF NOT EXISTS std_authenticity  DOUBLE PRECISION DEFAULT 0,
  ADD COLUMN IF NOT EXISTS std_avoidance     DOUBLE PRECISION DEFAULT 0,
  ADD COLUMN IF NOT EXISTS delay_count_total INTEGER          DEFAULT 0,
  ADD COLUMN IF NOT EXISTS auth_M2           DOUBLE PRECISION DEFAULT 0,
  ADD COLUMN IF NOT EXISTS avoid_M2          DOUBLE PRECISION DEFAULT 0;
-- auth_M2 / avoid_M2 = Welford running sum-of-squared-deviations
-- Required for incremental std dev without rescanning history

-- Backfill count for existing rows (optional, safe)
UPDATE user_analytics_summary
SET delay_count_total = total_delays
WHERE delay_count_total = 0 AND total_delays > 0;
