from flask import Blueprint, render_template, session, abort, current_app
from repository.db import test_connection, execute_query
import time
from utils.flask_auth import auth_required
from utils.task_enrichment import enrich_task

dashboard_bp = Blueprint('dashboard', __name__)

# ---------------------------------------------------------------------------
# Mega Query & Cache Configuration
# ---------------------------------------------------------------------------

_DASHBOARD_CACHE = {}  # {user_id: (data, expiry)}
_CACHE_TTL = 10        # seconds

def _fetch_dashboard_mega_package(user_id: int, role: str) -> dict:
    """Fetch all dashboard data in a single DB round trip using CTEs."""
    if role == 'employee':
        query = """
        WITH user_tasks AS (
            SELECT id, title, status, priority, deadline, created_at, predicted_risk as risk_score
            FROM tasks WHERE assigned_to = %s
        ),
        user_delays AS (
            SELECT id, score_authenticity, risk_level, submitted_at, reason_text
            FROM delays WHERE user_id = %s
        ),
        kpis AS (
            SELECT 
                COUNT(*) FILTER (WHERE status = 'Pending') as pending,
                COUNT(*) FILTER (WHERE status = 'Completed') as completed,
                COUNT(*) FILTER (WHERE status = 'Delayed') as delayed,
                COUNT(*) as total_tasks
            FROM user_tasks
        )
        SELECT json_build_object(
            'tasks', (SELECT json_agg(t) FROM (SELECT * FROM user_tasks ORDER BY created_at DESC) t),
            'delays', (SELECT json_agg(d) FROM (SELECT * FROM user_delays ORDER BY submitted_at DESC) d),
            'stats', (SELECT row_to_json(k) FROM kpis k)
        ) as dashboard_package;
        """
        params = (user_id, user_id)
    else:
        # Admin view: Fetch all
        query = """
        WITH all_tasks AS (
            SELECT id, title, status, priority, deadline, created_at, predicted_risk as risk_score
            FROM tasks
        ),
        all_delays AS (
            SELECT id, score_authenticity, risk_level, submitted_at, reason_text
            FROM delays
        ),
        kpis AS (
            SELECT 
                COUNT(*) FILTER (WHERE status = 'Pending') as pending,
                COUNT(*) FILTER (WHERE status = 'Completed') as completed,
                COUNT(*) FILTER (WHERE status = 'Delayed') as delayed,
                COUNT(*) as total_tasks
            FROM all_tasks
        )
        SELECT json_build_object(
            'tasks', (SELECT json_agg(t) FROM (SELECT * FROM all_tasks ORDER BY created_at DESC) t),
            'delays', (SELECT json_agg(d) FROM (SELECT * FROM all_delays ORDER BY submitted_at DESC) d),
            'stats', (SELECT row_to_json(k) FROM kpis k)
        ) as dashboard_package;
        """
        params = ()

    res = execute_query(query, params)
    if not res or not res[0]['dashboard_package']:
        return {'tasks': [], 'delays': [], 'stats': {}}
    
    pkg = res[0]['dashboard_package']
    # stats might be None if no tasks
    if not pkg['stats']:
        pkg['stats'] = {'pending': 0, 'completed': 0, 'delayed': 0, 'total_tasks': 0}
    
    # Authenticity average from delays
    delays = pkg.get('delays') or []
    scores = [d['score_authenticity'] for d in delays if d.get('score_authenticity') is not None]
    pkg['stats']['auth_score'] = round(sum(scores) / len(scores), 1) if scores else 0
    
    # Efficiency & Risk calculation
    total = pkg['stats']['total_tasks']
    comp = pkg['stats']['completed']
    pkg['stats']['efficiency'] = int((comp / total) * 100) if total > 0 else 0
    
    # Delay Index (Average risk across tasks)
    tasks = pkg.get('tasks') or []
    risk_scores = [t['risk_score'] for t in tasks if t.get('risk_score') is not None]
    pkg['stats']['risk_avg'] = round(sum(risk_scores) / len(risk_scores), 1) if risk_scores else 0

    # Real week-over-week trends for Efficiency, Audit, and Risk
    try:
        trend_query = """
            WITH this_week AS (
                SELECT
                    COUNT(*) FILTER (WHERE status = 'Completed') AS comp,
                    COUNT(*) AS total,
                    COALESCE(AVG(predicted_risk), 0) AS risk
                FROM tasks
                WHERE created_at >= NOW() - INTERVAL '7 days'
            ),
            last_week AS (
                SELECT
                    COUNT(*) FILTER (WHERE status = 'Completed') AS comp,
                    COUNT(*) AS total,
                    COALESCE(AVG(predicted_risk), 0) AS risk
                FROM tasks
                WHERE created_at >= NOW() - INTERVAL '14 days'
                  AND created_at < NOW() - INTERVAL '7 days'
            ),
            delays_this AS (
                SELECT COALESCE(AVG(score_authenticity), 0) AS auth
                FROM delays
                WHERE submitted_at >= NOW() - INTERVAL '7 days'
            ),
            delays_last AS (
                SELECT COALESCE(AVG(score_authenticity), 0) AS auth
                FROM delays
                WHERE submitted_at >= NOW() - INTERVAL '14 days'
                  AND submitted_at < NOW() - INTERVAL '7 days'
            )
            SELECT
                CASE WHEN tw.total > 0 THEN ROUND((tw.comp::float / tw.total) * 100) ELSE 0 END AS eff_this,
                CASE WHEN lw.total > 0 THEN ROUND((lw.comp::float / lw.total) * 100) ELSE 0 END AS eff_last,
                tw.risk AS risk_this,
                lw.risk AS risk_last,
                dt.auth AS auth_this,
                dl.auth AS auth_last
            FROM this_week tw, last_week lw, delays_this dt, delays_last dl
        """
        trend_res = execute_query(trend_query, ())
        if trend_res:
            r = trend_res[0]
            pkg['stats']['efficiency_trend'] = int((r.get('eff_this') or 0) - (r.get('eff_last') or 0))
            pkg['stats']['auth_trend'] = round((r.get('auth_this') or 0) - (r.get('auth_last') or 0), 1)
            pkg['stats']['risk_trend'] = round((r.get('risk_this') or 100) - (r.get('risk_last') or 100), 1) # Note: Risk is usually inverted in logic
        else:
            pkg['stats']['efficiency_trend'] = 0
            pkg['stats']['auth_trend'] = 0
            pkg['stats']['risk_trend'] = 0
    except Exception as e:
        print(f"Trend Query Error: {e}")
        pkg['stats']['efficiency_trend'] = 0
        pkg['stats']['auth_trend'] = 0
        pkg['stats']['risk_trend'] = 0

    return pkg


# ---------------------------------------------------------------------------
# Route
# ---------------------------------------------------------------------------

@dashboard_bp.route('/dashboard')
@auth_required
def dashboard():
    start_time = time.perf_counter()
    user_id   = session.get('user_id')
    user_role = session.get('user_role', 'employee')

    # @auth_required should guarantee user_id; fail loudly if the contract breaks.
    if not user_id:
        abort(401)

    # Safe defaults — dashboard will render even if every service fails
    tasks = []
    delays = []
    counts = {'pending': 0, 'completed': 0, 'delayed_tasks': 0,
              'total_delays': 0, 'total_tasks': 0, 'efficiency': 0, 'auth_score': 0,
              'efficiency_trend': 0, 'risk_avg': 0}
    active_tasks = []
    ai_insights = []
    analytics = {}
    diagnostics = None
    project_health = None
    enterprise_confidence = 0

    # 1. Fetch data (Mega Query + Cache)
    try:
        now = time.time()
        cache_key = f"{user_id}_{user_role}"
        
        if cache_key in _DASHBOARD_CACHE:
            pkg, expiry = _DASHBOARD_CACHE[cache_key]
            if now < expiry:
                # Cache HIT
                pass
            else:
                # Cache EXPIRED
                pkg = _fetch_dashboard_mega_package(user_id, user_role)
                _DASHBOARD_CACHE[cache_key] = (pkg, now + _CACHE_TTL)
        else:
            # Cache MISS
            pkg = _fetch_dashboard_mega_package(user_id, user_role)
            _DASHBOARD_CACHE[cache_key] = (pkg, now + _CACHE_TTL)

        tasks = pkg.get('tasks') or []
        delays = pkg.get('delays') or []
        stats = pkg.get('stats')

        counts = {
            'pending':          stats.get('pending', 0),
            'completed':        stats.get('completed', 0),
            'delayed_tasks':    stats.get('delayed', 0),
            'total_delays':     len(delays),
            'total_tasks':      stats.get('total_tasks', 0),
            'efficiency':       stats.get('efficiency', 0),
            'auth_score':       stats.get('auth_score', 0),
            'efficiency_trend': stats.get('efficiency_trend', 0),
            'auth_trend':       stats.get('auth_trend', 0),
            'risk_avg':         stats.get('risk_avg', 0),
            'risk_trend':       stats.get('risk_trend', 0),
        }

        # Optimization: Only enrich the tasks that are actually being shown on the dashboard (first 5).
        active_tasks = [t for t in tasks if t.get('status') in ('Pending', 'Delayed')]
        display_subset = active_tasks[:5]
        
        for task in display_subset:
            try:
                enrich_task(task)
            except Exception:
                pass
    except Exception as e:
        current_app.logger.error(f"Dashboard: Mega Query failed: {e}")

    # 2. Analytics & AI insights
    try:
        from services.analytics_service import get_analytics_data
        analytics = get_analytics_data(user_id=user_id, role=user_role)
        ai_insights = analytics.get('ai_insights', [])
        if 'efficiency' in analytics:
            counts['efficiency'] = analytics['efficiency']
    except Exception as e:
        current_app.logger.error(f"Dashboard: analytics failed: {e}")

    # 3. Diagnostics (admin only)
    try:
        diagnostics = test_connection() if user_role == 'admin' else None
    except Exception as e:
        current_app.logger.error(f"Dashboard: diagnostics failed: {e}")

    # 4. Risk service
    try:
        from services.risk_service import get_project_health_index, batch_predictive_risk
        project_health = get_project_health_index()
        task_ids = [t['id'] for t in display_subset if 'id' in t] # Subset for speed
        avg_risk = batch_predictive_risk(task_ids) if task_ids else 0.0
        enterprise_confidence = max(0, int(100 - avg_risk))
    except Exception as e:
        current_app.logger.error(f"Dashboard: risk service failed: {e}")

    duration = time.perf_counter() - start_time
    print(f"DEBUG: Dashboard route latency: {duration:.4f}s [User: {user_id}, Role: {user_role}]")

    return render_template(
        'dashboard.html',
        user_name=session.get('user_name'),
        counts=counts,
        tasks=tasks,
        active_tasks=display_subset,
        ai_insights=ai_insights,
        analytics=analytics,
        role=user_role,
        delays=delays,
        diagnostics=diagnostics,
        project_health=project_health,
        enterprise_confidence=enterprise_confidence
    )
