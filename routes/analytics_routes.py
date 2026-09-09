from flask import Blueprint, render_template, current_app, session, redirect, url_for
from utils.flask_auth import auth_required
from services.analytics_service import get_overview_data, get_ai_intelligence, get_trend_data

analytics_bp = Blueprint('analytics', __name__)

@analytics_bp.route('/analytics')
@auth_required
def analytics_root():
    """Redirect root analytics to overview."""
    return redirect(url_for('analytics.analytics_overview'))

@analytics_bp.route('/analytics/overview')
@auth_required
def analytics_overview():
    """Render the analytics overview (gauges, risk)."""
    user_id = session.get('user_id')
    role = session.get('user_role', 'employee')
    is_management = role in ('admin', 'manager')

    stats = {}
    tri = {}
    contagion_alerts = []
    error = None

    try:
        from services.analytics_service import get_team_resilience_index, detect_behavioral_contagion
        stats = get_overview_data(user_id, role)
        
        # Fetch AI intelligence and merge it into stats for the gauges
        ai_intel = get_ai_intelligence(user_id, role)
        
        # Safe merge to protect core metrics from any AI key collisions
        stats = {
            **stats,
            **{
                "ai": ai_intel.get("ai", {}),
                "ai_insights": ai_intel.get("ai_insights", []),
                "executive_summary": ai_intel.get("executive_summary", ""),
                "processing": ai_intel.get("processing", False),
            }
        }
        
        # Tier 5: Collective Intelligence (Management only)
        if is_management:
            tri = get_team_resilience_index()
            contagion_alerts = detect_behavioral_contagion()
            
    except Exception as e:
        import traceback
        current_app.logger.error("Analytics overview error: %s\n%s", e, traceback.format_exc())
        error = "Failed to load overview data"

    return render_template(
        'analytics_overview.html',
        stats=stats,
        tri=tri,
        contagion_alerts=contagion_alerts,
        error=error,
        role=role,
        is_management=is_management,
        active_tab='overview'
    )


@analytics_bp.route('/analytics/ai')
@auth_required
def analytics_ai():
    """Render the AI intelligence dashboard."""
    user_id = session.get('user_id')
    role = session.get('user_role', 'employee')
    is_management = role in ('admin', 'manager')

    template_context = {
        'role': role,
        'is_management': is_management,
        'active_tab': 'ai',
        'data': {},
        'error': None
    }

    try:
        data = get_ai_intelligence(user_id, role)
        template_context['data'] = data
    except Exception as e:
        current_app.logger.error("Analytics AI error: %s", e)
        template_context['error'] = "Failed to load AI data"

    return render_template('analytics_ai.html', **template_context)


@analytics_bp.route('/analytics/trends')
@auth_required
def analytics_trends():
    """Render the trends dashboard."""
    user_id = session.get('user_id')
    role = session.get('user_role', 'employee')
    is_management = role in ('admin', 'manager')

    template_context = {
        'role': role,
        'is_management': is_management,
        'active_tab': 'trends',
        'data': {},
        'error': None
    }

    try:
        data = get_trend_data(user_id, role)
        template_context['data'] = data
    except Exception as e:
        current_app.logger.error("Analytics trends error: %s", e)
        template_context['error'] = "Failed to load trend data"

    return render_template('analytics_trends.html', **template_context)
