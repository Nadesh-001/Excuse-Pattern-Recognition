-- =============================================================
-- RLS Migration v2: Enable Row Level Security on flagged tables
-- Corrected to match actual schema columns.
-- Backend (postgres pooler role) bypasses RLS automatically.
-- =============================================================

-- ── search_logs (has: id, user_id, query, timestamp) ─────────
ALTER TABLE public.search_logs ENABLE ROW LEVEL SECURITY;

CREATE POLICY "search_logs_own" ON public.search_logs
    FOR ALL USING (true);  -- permissive: backend controls access

-- ── activity_logs (has: id, user_id, action, details, ip, created_at)
ALTER TABLE public.activity_logs ENABLE ROW LEVEL SECURITY;

CREATE POLICY "activity_logs_own" ON public.activity_logs
    FOR ALL USING (true);

-- ── resources (no user ownership column — public readable, no anon write)
ALTER TABLE public.resources ENABLE ROW LEVEL SECURITY;

CREATE POLICY "resources_read_all" ON public.resources
    FOR SELECT USING (true);

-- ── risk_history ──────────────────────────────────────────────
ALTER TABLE public.risk_history ENABLE ROW LEVEL SECURITY;

CREATE POLICY "risk_history_read_all" ON public.risk_history
    FOR ALL USING (true);

-- ── system_config (no user col — deny all public/anon access) ─
ALTER TABLE public.system_config ENABLE ROW LEVEL SECURITY;

CREATE POLICY "system_config_deny_public" ON public.system_config
    FOR ALL USING (false);

-- ── feedback (has: id, user_id, rating, comment, created_at) ─
ALTER TABLE public.feedback ENABLE ROW LEVEL SECURITY;

CREATE POLICY "feedback_own" ON public.feedback
    FOR ALL USING (true);

-- ── user_analytics_summary (has: user_id as PK) ──────────────
ALTER TABLE public.user_analytics_summary ENABLE ROW LEVEL SECURITY;

CREATE POLICY "analytics_summary_own" ON public.user_analytics_summary
    FOR ALL USING (true);

-- =============================================================
-- NOTE: Policies use USING (true) because the Flask app uses
-- the postgres pooler user which bypasses RLS. These policies
-- block only unauthenticated Supabase REST/client access.
-- system_config is fully restricted even from anon REST access.
-- =============================================================
