"""
report_routes.py
================
Blueprint providing 4 report endpoints:
  - GET /report/task/<task_id>/view        → in-app A4 view (single task)
  - GET /report/task/<task_id>/download    → PDF download (single task)
  - GET /report/user/<user_id>/view        → in-app consolidated user view
  - GET /report/user/<user_id>/download    → PDF download (consolidated user)

Access control:
  - admin / manager → full access
  - employee        → task reports only for assigned tasks; no user reports
"""

from flask import Blueprint, render_template, session, abort, current_app
from utils.flask_auth import auth_required

report_bp = Blueprint("reports", __name__)


def _current_user():
    return session.get("user_id"), session.get("user_role", "employee")


# ---------------------------------------------------------------------------
# Task Report — View
# ---------------------------------------------------------------------------

@report_bp.route("/report/task/<int:task_id>/view")
@auth_required
def task_report_view(task_id: int):
    user_id, role = _current_user()
    if not user_id:
        abort(401)
    try:
        from services.report_service import build_task_report_data
        data = build_task_report_data(task_id, user_id, role)
    except LookupError as e:
        current_app.logger.warning("Report 404: %s", e)
        abort(404)
    except PermissionError as e:
        current_app.logger.warning("Report 403: %s", e)
        abort(403)
    except Exception as e:
        import traceback
        with open("task_report_crash.txt", "w") as f:
            f.write(traceback.format_exc())
        current_app.logger.error("Report build error for task %s: %s", task_id, e, exc_info=True)
        abort(500)

    print(f"DEBUG: Task {task_id} data build successful")
    return render_template("report_task_view.html", r=data, task_id=task_id)


# ---------------------------------------------------------------------------
# Task Report — PDF Download
# ---------------------------------------------------------------------------

@report_bp.route("/report/task/<int:task_id>/download")
@auth_required
def task_report_download(task_id: int):
    user_id, role = _current_user()
    if not user_id:
        abort(401)
    try:
        from services.report_service import build_task_report_data
        from services.pdf_service import generate_task_report_pdf
        data = build_task_report_data(task_id, user_id, role)
        return generate_task_report_pdf(data)
    except LookupError:
        abort(404)
    except PermissionError:
        abort(403)
    except Exception as e:
        current_app.logger.error("PDF generation error for task %s: %s", task_id, e, exc_info=True)
        abort(500)


# ---------------------------------------------------------------------------
# Consolidated User Report — View
# ---------------------------------------------------------------------------

@report_bp.route("/report/user/<int:user_id>/view")
@auth_required
def user_report_view(user_id: int):
    current_uid, role = _current_user()
    if not current_uid:
        abort(401)
    try:
        from services.report_service import build_user_report_data
        data = build_user_report_data(user_id, current_uid, role)
    except LookupError as e:
        current_app.logger.warning("User report 404: %s", e)
        abort(404)
    except PermissionError as e:
        current_app.logger.warning("User report 403: %s", e)
        abort(403)
    except Exception as e:
        import traceback
        with open("crash_traceback.txt", "w") as f:
            f.write(traceback.format_exc())
        current_app.logger.error("User report error for user %s: %s", user_id, e, exc_info=True)
        abort(500)

    return render_template("report_user_view.html", r=data, target_user_id=user_id)


# ---------------------------------------------------------------------------
# Consolidated User Report — PDF Download
# ---------------------------------------------------------------------------

@report_bp.route("/report/user/<int:user_id>/download")
@auth_required
def user_report_download(user_id: int):
    current_uid, role = _current_user()
    if not current_uid:
        abort(401)
    try:
        from services.report_service import build_user_report_data
        from services.pdf_service import generate_user_report_pdf
        data = build_user_report_data(user_id, current_uid, role)
        return generate_user_report_pdf(data)
    except LookupError:
        abort(404)
    except PermissionError:
        abort(403)
    except Exception as e:
        current_app.logger.error("User PDF error for user %s: %s", user_id, e, exc_info=True)
        abort(500)
