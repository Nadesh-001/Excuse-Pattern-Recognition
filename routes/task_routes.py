from flask import Blueprint, render_template, request, redirect, url_for, session, flash, current_app, make_response, jsonify
from utils.flask_auth import auth_required, manager_required
from utils.task_enrichment import enrich_task
from services.task_service import (
    service_get_tasks,
    service_create_task,
    service_complete_task,
    service_submit_delay,
    service_delete_task,
    service_get_task_or_404,
)
from repository.resources_repo import get_resources_by_task, create_resource
from services.user_service import get_users_list
from services.activity_service import log_activity

tasks_bp = Blueprint('tasks', __name__)

# ---------------------------------------------------------------------------
# File upload policy — constants at module level, not per-request.
# ---------------------------------------------------------------------------

ALLOWED_EXTENSIONS = {'pdf', 'png', 'jpg', 'jpeg', 'doc', 'docx'}
MAX_FILE_SIZE      = 10 * 1024 * 1024  # 10 MB


def _validate_proof_file(proof_file) -> str | None:
    """
    Validate extension and size of an uploaded proof file.

    Returns an error message string, or None if the file is valid (or absent).
    """
    if not proof_file or not proof_file.filename:
        return None

    ext = proof_file.filename.rsplit('.', 1)[-1].lower() if '.' in proof_file.filename else ''
    if ext not in ALLOWED_EXTENSIONS:
        return f"Invalid file type. Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS)).upper()}"

    # Seek/tell is acceptable here because Werkzeug has already buffered the
    # upload. We reset the position so the service layer reads from byte 0.
    proof_file.seek(0, 2)
    size = proof_file.tell()
    proof_file.seek(0)
    if size > MAX_FILE_SIZE:
        return "File too large. Maximum 10 MB allowed."

    return None


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@tasks_bp.route('/')
@auth_required
def tasks():
    user_id = session.get('user_id')
    role = session.get('user_role', 'employee')
    
    # Fetch tasks
    tasks_list = service_get_tasks(user_id, role) or []

    # Parsing filters
    status_filter = request.args.get('status')
    if status_filter and status_filter != 'All':
        tasks_list = [t for t in tasks_list if t['status'] == status_filter]

    priority_filter = request.args.get('priority')
    if priority_filter and priority_filter != 'All':
        tasks_list = [t for t in tasks_list if t['priority'] == priority_filter]

    search_query = request.args.get('q', '').lower().strip()
    if search_query:
        tasks_list = [
            t for t in tasks_list
            if search_query in (t.get('title') or '').lower()
            or search_query in (t.get('description') or '').lower()
        ]

    for task in tasks_list:
        enrich_task(task)

    return render_template('tasks.html', tasks=tasks_list, role=role)


@tasks_bp.route('/new', methods=['GET', 'POST'])
@manager_required
def new_task():
    if request.method == 'POST':
        title       = request.form.get('title', '').strip()
        description = request.form.get('description', '').strip()
        assigned_to = request.form.get('assigned_to', '').strip()
        deadline    = request.form.get('deadline')
        priority    = request.form.get('priority', 'Medium')
        category    = request.form.get('category', 'General')

        try:
            est_hours   = int(request.form.get('est_hours')   or 0)
            est_minutes = int(request.form.get('est_minutes') or 0)
            complexity  = int(request.form.get('complexity')  or 1)
        except (ValueError, TypeError):
            flash("Invalid estimated time. Please enter valid numbers.", "error")
            return render_template('task_form.html', users=get_users_list(session['user_id']))

        if not (title and description and assigned_to):
            flash("Title, description, and assignee are required.", "warning")
            return render_template('task_form.html', users=get_users_list(session['user_id']))

        try:
            task_id = service_create_task(
                manager_id  = session['user_id'],
                title       = title,
                description = description,
                assigned_to = int(assigned_to),
                priority    = priority,
                deadline    = deadline,
                est_hours   = est_hours,
                est_minutes = est_minutes,
                category    = category,
                complexity  = complexity
            )
            # Log Activity
            log_activity(session['user_id'], "TASK_CREATE", f"Created task: {title}")
            
            current_app.logger.info("Task created — id: %s  manager: %s", task_id, session['user_id'])
            flash("Task created successfully!", "success")
            return redirect(url_for('tasks.tasks'))
        except (ValueError, TypeError) as e:
            flash(f"Invalid assignment or time data: {e}", "error")
        except Exception as e:
            current_app.logger.error("Task creation error: %s", e)
            flash("Error creating task. Please try again.", "error")

    # Render form with fresh user list and cache-control headers
    response = make_response(render_template('task_form.html', users=get_users_list(session['user_id'])))
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response


@tasks_bp.route('/<int:task_id>')
@auth_required
def task_details(task_id):
    # Ownership / existence check is the service's responsibility.
    task = service_get_task_or_404(task_id)
    resources = get_resources_by_task(task_id)

    from repository.delays_repo import get_delays_by_task
    delays = get_delays_by_task(task_id)
    
    # Tier 3: Parse analysis JSON for UI flags
    import json
    for d in delays:
        analysis = d.get('ai_analysis_json')
        if isinstance(analysis, str):
            try: d['ai_analysis'] = json.loads(analysis)
            except: d['ai_analysis'] = {}
        else:
            d['ai_analysis'] = analysis or {}


    # --- Neural Intelligence Integration (v1.0) ---
    intelligence = {}
    try:
        from services.analytics_service import get_task_intelligence
        intelligence = get_task_intelligence(task_id)
    except Exception as e:
        current_app.logger.error("Neural intelligence unavailable for task %s: %s", task_id, e)

    return render_template('task_details.html',
                          task=task,
                          resources=resources,
                          delays=delays,
                          intelligence=intelligence)


@tasks_bp.route('/<int:task_id>/complete', methods=['POST'])
@auth_required
def complete_task(task_id):
    user_id = session.get('user_id')
    try:
        service_complete_task(user_id, task_id)
        log_activity(user_id, "TASK_COMPLETE", f"Completed task ID: {task_id}")
        flash("Task completed successfully!", "success")
    except LookupError:
        flash("Task not found.", "error")
        return redirect(url_for('tasks.tasks'))
    except PermissionError as e:
        flash(str(e), "error")
    except Exception as e:
        current_app.logger.error("Error completing task %s: %s", task_id, e, exc_info=True)
        flash(f"Error completing task: {e}", "error")

    return redirect(url_for('tasks.task_details', task_id=task_id))


@tasks_bp.route('/<int:task_id>/delay', methods=['POST'])
@auth_required
def submit_delay(task_id):
    try:
        user_id = session.get('user_id')

        reason     = request.form.get('reason', '').strip()
        proof_file = request.files.get('proof')

        if not reason:
            flash("A reason is required.", "warning")
            return redirect(url_for('tasks.task_details', task_id=task_id))

        file_error = _validate_proof_file(proof_file)
        if file_error:
            flash(file_error, "error")
            return redirect(url_for('tasks.task_details', task_id=task_id))

        result = service_submit_delay(
            user_id    = user_id,
            task_id    = task_id,
            reason     = reason,
            proof_file = proof_file,
        )
        
        flash("Excuse submitted successfully!", "success")
        verdict_obj = result.get('verdict') # This might be the label or a dict
        if isinstance(verdict_obj, dict):
            verdict_obj.get('verdict', 'UNKNOWN')
            fake_score = verdict_obj.get('fake_score', 0)
        else:
            str(verdict_obj or 'UNKNOWN')
            fake_score = result.get('authenticity_score', 0)
            
        flash(
            f"Authenticity Score: {fake_score}/100 — Risk: {result.get('risk_level', 'Unknown')}",
            "info",
        )
        
        # Log Activity
        log_activity(user_id, "DELAY_SUBMIT", f"Submitted excuse for task ID: {task_id}")
        
        return redirect(url_for('tasks.task_details', task_id=task_id))

    except PermissionError as e:
        flash(str(e), "error")
    except LookupError:
        flash("Task not found.", "error")
        return redirect(url_for('tasks.tasks'))
    except Exception as e:
        current_app.logger.error("Error submitting delay for task %s: %s", task_id, e, exc_info=True)
        flash(f"Error submitting delay: {e}", "error")

    return redirect(url_for('tasks.task_details', task_id=task_id))


@tasks_bp.route('/<int:task_id>/delete', methods=['POST'])
@auth_required
def delete_task(task_id):
    user_id = session.get('user_id')
    try:
        service_delete_task(user_id, task_id, session.get('user_role', 'employee'))
        log_activity(user_id, "TASK_DELETE", f"Deleted task ID: {task_id}")
        flash("Task deleted successfully!", "success")
    except PermissionError as e:
        flash(str(e), "error")
    except LookupError:
        flash("Task not found.", "error")
    except Exception as e:
        current_app.logger.error("Error deleting task %s: %s", task_id, e)
        flash("Error deleting task. Please try again.", "error")

    return redirect(url_for('tasks.tasks'))

@tasks_bp.route('/<int:task_id>/upload', methods=['POST'])
@auth_required
def upload_task_document(task_id):
    """Upload a supporting document directly to a task (not delay-specific)."""
    user_id = session.get('user_id')
    role    = session.get('user_role', 'employee')

    task = service_get_task_or_404(task_id)

    # Only assignee, manager, or admin may upload
    if role not in ('admin', 'manager') and task.get('assigned_to') != user_id:
        flash("You do not have permission to upload documents for this task.", "error")
        return redirect(url_for('tasks.task_details', task_id=task_id))

    doc_file = request.files.get('document')
    if not doc_file or not doc_file.filename:
        flash("Please select a file to upload.", "warning")
        return redirect(url_for('tasks.task_details', task_id=task_id))

    file_error = _validate_proof_file(doc_file)
    if file_error:
        flash(file_error, "error")
        return redirect(url_for('tasks.task_details', task_id=task_id))

    try:
        from services.upload_service import upload_file
        result = upload_file(doc_file, folder=f"tasks/{task_id}")
        if not result.get('success'):
            flash(f"Upload failed: {result.get('error', 'Unknown error')}", "error")
            return redirect(url_for('tasks.task_details', task_id=task_id))

        create_resource(
            task_id            = task_id,
            resource_type      = 'document',
            url_or_path        = result['path'],
            title              = doc_file.filename,
            ai_summary         = 'Pending AI',
            requirements_json  = {},
            deadlines_json     = {},
            completeness_score = 0,
        )
        log_activity(user_id, "DOC_UPLOAD", f"Uploaded document '{doc_file.filename}' for task {task_id}")
        flash(f"Document '{doc_file.filename}' uploaded successfully.", "success")
    except Exception as e:
        current_app.logger.error("Document upload error task %s: %s", task_id, e, exc_info=True)
        flash("An error occurred during upload. Please try again.", "error")

    return redirect(url_for('tasks.task_details', task_id=task_id))


@tasks_bp.route('/suggest-attributes', methods=['POST'])
@auth_required
def suggest_attributes():
    """Returns AI-suggested priority and category based on title and description."""
    data = request.get_json(silent=True)  # silent=True returns None instead of 400 on bad Content-Type
    if not data:
        return jsonify({"error": "JSON body required"}), 400

    title = data.get('title', '').strip()
    description = data.get('description', '')

    if not title:
        return jsonify({"error": "Title is required"}), 400

    try:
        from services.nlp_service import suggest_task_attributes
        suggestions = suggest_task_attributes(title, description)
    except Exception as e:
        current_app.logger.error("suggest_attributes error: %s", e)
        return jsonify({"error": "AI suggestion service unavailable"}), 503

    # Add feasibility check if est_minutes and user_id are provided
    est_mins = data.get('estimated_minutes')
    user_id = data.get('user_id')
    if est_mins is not None and user_id:
        try:
            from services.risk_service import validate_task_feasibility
            risk_score, risk_msg = validate_task_feasibility(title, description, int(est_mins), int(user_id))
            suggestions['feasibility_risk'] = risk_score
            suggestions['feasibility_msg'] = risk_msg
        except (ValueError, TypeError):
            pass  # Invalid int values — skip feasibility check
        except Exception as e:
            current_app.logger.warning("Feasibility check failed: %s", e)

    return jsonify(suggestions)
@tasks_bp.route('/delay/<int:delay_id>/delete', methods=['POST'])
@auth_required
def delete_delay(delay_id):
    user_id = session.get('user_id')
    role    = session.get('user_role', 'employee')
    task_id = request.args.get('task_id') # To redirect back
    
    try:
        from services.task_service import service_delete_delay
        service_delete_delay(user_id, delay_id, role)
        flash("Delay record deleted.", "success")
    except Exception as e:
        current_app.logger.error("Error deleting delay %s: %s", delay_id, e)
        flash("Could not delete delay record.", "error")
        
    if task_id:
        return redirect(url_for('tasks.task_details', task_id=task_id))
    return redirect(url_for('tasks.tasks'))
