from flask import Blueprint, render_template, redirect, url_for, flash, current_app
from utils.flask_auth import manager_required
from repository.users_repo import get_all_users, get_user_by_id
from services.analytics_service import get_analytics_data
from repository.tasks_repo import get_tasks_by_user

team_bp = Blueprint('team', __name__)

@team_bp.route('/team')
@manager_required
def team_directory():
    """Shows all employees with summarized risk profiles."""
    try:
        users = get_all_users(active_only=True)
        employees = [u for u in users if u['role'] == 'employee']
        
        if employees:
            emp_ids = [e['id'] for e in employees]
            
            # Batch: get delay counts and avg authenticity per user (2 queries total)
            from repository.db import execute_query
            delay_stats = execute_query(
                """SELECT user_id,
                          COUNT(*) as delay_count,
                          AVG(score_authenticity) as avg_auth
                   FROM delays
                   WHERE user_id = ANY(%s)
                   GROUP BY user_id""",
                (emp_ids,), fetch=True
            ) or []
            
            stats_map = {row['user_id']: row for row in delay_stats}
            
            for emp in employees:
                row = stats_map.get(emp['id'], {})
                emp['avg_auth'] = round(row.get('avg_auth', 0) or 0, 1)
                emp['delay_count'] = row.get('delay_count', 0) or 0
                emp['risk_level'] = "High" if emp['avg_auth'] < 45 else ("Medium" if emp['avg_auth'] < 75 else "Low")
            
        return render_template('team_directory.html', employees=employees)
    except Exception as e:
        current_app.logger.error(f"Team directory error: {e}")
        return redirect(url_for('dashboard.dashboard'))

@team_bp.route('/team/user/<int:user_id>')
@manager_required
def employee_profile(user_id):
    """Detailed drill-down of a single employee's performance."""
    try:
        user = get_user_by_id(user_id)
        if not user or user['role'] != 'employee':
            flash("Employee not found.", "error")
            return redirect(url_for('team.team_directory'))
            
        stats = get_analytics_data(user_id=user_id, role='employee')
        tasks = get_tasks_by_user(user_id)
        
        return render_template('employee_profile.html', 
                             employee=user, 
                             stats=stats, 
                             graphs=stats.get('graphs', {}),
                             tasks=tasks)
    except Exception as e:
        current_app.logger.error(f"Employee profile error: {e}")
        return redirect(url_for('team.team_directory'))
