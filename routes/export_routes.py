from flask import Blueprint, session, request, flash, redirect, url_for, current_app
from utils.flask_auth import auth_required
from services.export_service import (
    generate_csv_report, 
    generate_word_report, 
    generate_pdf_report,
    generate_analytics_pdf_report
)

export_bp = Blueprint('export', __name__)

@export_bp.route('/export')
@auth_required
def export_report():
    """Generic endpoint for downloading reports in various formats."""
    user_id = session.get('user_id')
    role = session.get('user_role', 'employee')
    
    # Parameters
    report_type = request.args.get('type', 'tasks') # 'tasks' or 'delays'
    fmt = request.args.get('format', 'csv').lower() # 'csv', 'docx', 'pdf'
    
    try:
        if fmt == 'csv':
            return generate_csv_report(user_id=user_id, role=role, type=report_type)
        elif fmt == 'docx' or fmt == 'word':
            return generate_word_report(user_id=user_id, role=role, type=report_type)
        elif fmt == 'pdf':
            return generate_pdf_report(user_id=user_id, role=role, type=report_type)
        else:
            flash(f"Unsupported format: {fmt}", "error")
            return redirect(url_for('dashboard.dashboard'))
    except Exception as e:
        current_app.logger.error(f"Export error: {e}")
        flash(f"Failed to generate {fmt.upper()} report", "error")
        return redirect(url_for('dashboard.dashboard'))

@export_bp.route('/export/analytics')
@auth_required
def export_analytics():
    """Generates the comprehensive PDF analytics report."""
    user_id = session.get('user_id')
    role = session.get('user_role', 'employee')
    
    try:
        return generate_analytics_pdf_report(user_id=user_id, role=role)
    except Exception as e:
        current_app.logger.error(f"Analytics export error: {e}")
        flash("Failed to generate comprehensive analytics report", "error")
        return redirect(url_for('analytics.analytics_overview'))

# Legacy route for backward compatibility if needed
@export_bp.route('/export/csv')
@auth_required
def export_csv():
    return redirect(url_for('export.export_report', format='csv', type=request.args.get('type', 'tasks')))
