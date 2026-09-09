from flask import current_app, abort
from repository.tasks_repo import (
    create_task, get_tasks_by_user, get_all_tasks, 
    update_task_status, get_task_by_id, update_task_completion, 
    delete_task as repo_delete_task
)
from repository.resources_repo import create_resource
from repository.delays_repo import create_delay, get_user_delay_history
from services.activity_service import log_activity
from utils.time_utils import parse_time_input
from utils.scoring_engine import calculate_authenticity_score
from utils.task_formulas import (
    calculate_task_status,
    is_task_delayed,
    calculate_elapsed_between,
)
from datetime import datetime, date
import json

def service_create_task(manager_id, title, description, assigned_to, priority, deadline, est_hours, est_minutes, category="General", links=None, complexity=1):
    """Create a new task with Enterprise Risk Monitoring integration."""
    from services.risk_service import calculate_predictive_risk, validate_task_feasibility
    
    est_total_mins = parse_time_input(est_hours, est_minutes)
    
    # 1. Feasibility check
    feasibility_score, feasibility_msg = validate_task_feasibility(title, description, est_total_mins, assigned_to)
    
    # 2. Initial risk calculation
    # We do a temporary create in logic if needed, but here we'll just prep fields
    # Task ID isn't known yet, so we pass a placeholder or adapt risk engine
    
    task_id = create_task(title, description, assigned_to, manager_id, priority, deadline, est_total_mins, complexity=complexity, category=category)
    
    # 3. Post-creation risk update
    risk_score, factors = calculate_predictive_risk(task_id)
    from repository.tasks_repo import update_task_risk
    update_task_risk(task_id, risk_score, factors)
    
    if links:
         for link in links:
              create_resource(task_id, 'link', link, 'External Link', 'Pending AI', {}, {}, 0)
              
    log_activity(manager_id, "CREATE_TASK", f"Created task '{title}' for user {assigned_to}. Risk: {risk_score}%")
    return task_id

def service_get_tasks(user_id, role):
    """Fetch tasks based on user role."""
    if role in ['admin', 'manager']:
        return get_all_tasks() or []
    return get_tasks_by_user(user_id) or []

def service_get_task_or_404(task_id):
    """Retrieve task by ID or raise Flask 404."""
    task = get_task_by_id(task_id)
    if not task:
        abort(404)
    return task

def _verify_task_ownership(user_id, role, task):
    """Raise PermissionError if user doesn't have access to the task."""
    if role in ['admin', 'manager']:
        return
    if task['assigned_to'] != user_id:
        raise PermissionError("You do not have permission to access this task.")

def service_complete_task(user_id, task_id):
    """Complete a task and log activity."""
    task = get_task_by_id(task_id)
    if not task:
        raise LookupError(f"Task {task_id} not found")
    
    # Ownership check
    if task['assigned_to'] != user_id:
        raise PermissionError("Only the assignee can complete this task.")
        
    completion_time = datetime.now()
    created_at = task['created_at']
    elapsed = calculate_elapsed_between(created_at, completion_time)
    elapsed_minutes = int(elapsed.total_seconds() / 60)
    estimated_minutes = task.get('estimated_minutes', 0)
    
    status = calculate_task_status(elapsed_minutes, estimated_minutes)
    update_task_completion(task_id, completion_time, status)
    
    # Update user reliability after completion
    from services.user_service import refresh_user_reliability
    refresh_user_reliability(user_id)
    
    log_activity(user_id, "COMPLETE_TASK", f"Completed task '{task['title']}' - Status: {status}")
    
    is_delayed_bool = is_task_delayed(elapsed_minutes, estimated_minutes)
    return {
        'status': status,
        'delayed': is_delayed_bool,
        'elapsed_minutes': elapsed_minutes,
        'estimated_minutes': estimated_minutes
    }

def service_submit_delay(user_id, task_id, reason, proof_file=None):
    """
    Submit delay analysis using the TaskIntelligenceEngine (v1.1).
    Governance Level C: Behavioral Modeling.
    """
    from services.intelligence_engine import TaskIntelligenceEngine
    from services.ai_service import analyze_excuse_with_ai
    
    task = get_task_by_id(task_id)
    if not task: raise LookupError("Task not found")
    if task['assigned_to'] != user_id: raise PermissionError("Unauthorized signal submission.")

    # 1. Initialize Intelligence Engine
    engine = TaskIntelligenceEngine(user_id)
    
    # 2. Contextual Telemetry (Deadline vs Submission)
    history = get_user_delay_history(user_id, limit=10)
    deadline_val = task.get('deadline')
    pressure   = 0
    delay_days = 0
    deadline_dt = None
    hours_left  = 48   # safe default (no penalty)

    if deadline_val:
        try:
            # psycopg2 with RealDictCursor returns deadline as a date/datetime
            # object — NOT a string. Handle all three cases defensively.
            if isinstance(deadline_val, datetime):
                deadline_dt = deadline_val
            elif isinstance(deadline_val, date):
                deadline_dt = datetime.combine(deadline_val, datetime.min.time())
            else:
                # Fallback: attempt string parse
                deadline_dt = datetime.strptime(str(deadline_val), "%Y-%m-%d")

            now  = datetime.now()
            diff = deadline_dt - now
            hours_left = diff.total_seconds() / 3600
            # Pressure: 100 = right at/past deadline, 0 = 3+ days away
            pressure = max(0, min(100, (1.0 - (diff.total_seconds() / 86400 / 3)) * 100))
            if diff.total_seconds() < 0:
                delay_days = abs(int(diff.total_seconds() / 86400))
        except Exception as _dl_err:
            current_app.logger.warning(
                "Deadline parse error for task %s: %s", task_id, _dl_err
            )

    # 3. Deterministic Feature Extraction (Independent of AI)
    engine.extract_features(reason, delay_days, pressure, history)
    
    # 4. Scoring & Flags (Rule-based)
    risk_score = engine.compute_task_risk()
    flags      = engine.trigger_flags()
    confidence = engine.compute_confidence(len(history))
    
    # 5. AI Interpretive Layer (Executive Insight)
    ai_analysis = analyze_excuse_with_ai(reason)

    # 5b. Deterministic verdict via scoring engine
    #     Map intelligence risk_score → authenticity, then classify verdict.
    authenticity = max(0, min(100, int(100 - risk_score)))
    ai_boost     = max(0, min(15, int((100 - risk_score) / 100 * 15)))
    score_bd = calculate_authenticity_score(
        reason            = reason,
        delay_count       = len(history),
        priority          = task.get('priority', 'Medium'),
        hours_left        = int(hours_left),
        has_proof         = bool(proof_file),
        is_after_deadline = delay_days > 0,
        ai_score          = ai_boost,
    )
    verdict = score_bd.verdict          # 'REAL' | 'SUSPICIOUS' | 'FAKE'
    authenticity = score_bd.total       # use the composite score

    # 6. Generate Governance Snapshot (includes verdict + per-delay feature vector)
    from services.risk_service import calculate_user_reliability
    reliability = calculate_user_reliability(user_id)
    snapshot = engine.generate_snapshot(confidence, reliability_index=reliability)
    snapshot['ai_interpretation'] = ai_analysis
    snapshot['verdict']           = verdict
    snapshot['authenticity_score'] = authenticity
    snapshot['score_breakdown']   = {
        'text':      score_bd.text,
        'history':   score_bd.history,
        'task':      score_bd.task,
        'proof':     score_bd.proof,
        'timing':    score_bd.timing,
        'ai_signal': score_bd.ai_signal,
        'total':     score_bd.total,
        'risk':      score_bd.risk,
        'verdict':   score_bd.verdict,
    }
    
    # 7. Persistence
    final_proof_path = None
    if proof_file:
        from services.upload_service import upload_file
        res = upload_file(proof_file, folder="proofs")
        if res['success']: final_proof_path = res['path']

    create_delay(
        task_id=task_id, 
        user_id=user_id, 
        reason_text=reason, 
        reason_audio_path=None,
        score_authenticity=authenticity,
        score_avoidance=risk_score,
        risk_level=score_bd.risk,
        ai_feedback=json.dumps({"engine_v": "1.1", "confidence": confidence, "verdict": verdict}),
        ai_analysis_json=json.dumps(snapshot),
        delay_duration=delay_days, 
        proof_path=final_proof_path
    )
    
    update_task_status(task_id, 'Delayed')
    
    # 8. Evolutionary Record (Trajectory Tracking)
    try:
        from database.connection import get_db_cursor
        with get_db_cursor() as cur:
            cur.execute(
                "INSERT INTO risk_history (user_id, task_id, risk_score, recorded_at) VALUES (%s, %s, %s, NOW())",
                (user_id, task_id, risk_score)
            )
    except Exception as e:
        current_app.logger.warning("Failed to record risk history for task %s: %s", task_id, e)

    # 9. Evolving Intelligence (User-Level Aggregation)
    from services.user_service import refresh_user_reliability
    refresh_user_reliability(user_id)
    
    # 10. Proactive Cache Refill (Pre-warming Dashboard)
    try:
        from services.analytics_service import trigger_async_refill
        from repository.users_repo import get_user_by_id
        user = get_user_by_id(user_id)
        role = user.get('role', 'employee') if user else 'employee'
        trigger_async_refill(user_id, role)
        current_app.logger.info("Proactive AI refill enqueued for user %s with role %s", user_id, role)
    except Exception as e:
        current_app.logger.warning("Failed to trigger proactive refill: %s", e)
    
    log_activity(user_id, "SUBMIT_DELAY", f"Task {task_id} Risk: {risk_score}% | Verdict: {verdict} | Flags: {len(flags)}")
    
    return {
        "risk_score":        risk_score,
        "authenticity_score": authenticity,
        "verdict":           verdict,
        "flags":             flags,
        "confidence":        confidence,
        "risk_level":        score_bd.risk,
    }

def service_delete_task(user_id, task_id, role):
    """Deletes a task with permission enforcement."""
    task = get_task_by_id(task_id)
    if not task:
        raise LookupError("Task not found")
        
    if role not in ['admin', 'manager'] and task['assigned_to'] != user_id:
        raise PermissionError("You do not have permission to delete this task")
        
    repo_delete_task(task_id)
    log_activity(user_id, "DELETE_TASK", f"Deleted task '{task['title']}'")
    return True
def service_delete_delay(user_id, delay_id, role):
    """Deletes a delay record with permission enforcement."""
    from repository.delays_repo import delete_delay as repo_delete_delay
    from repository.delays_repo import get_delay_by_id
    
    # 1. Fetch targeted delay
    target_delay = get_delay_by_id(delay_id)
    
    if not target_delay:
        current_app.logger.warning("Attempted to delete non-existent delay %s by user %s", delay_id, user_id)
        raise LookupError("Delay record not found")
        
    # 2. Permission check
    if role not in ['admin', 'manager'] and target_delay['user_id'] != user_id:
        current_app.logger.error("Unauthorized deletion attempt for delay %s by user %s", delay_id, user_id)
        raise PermissionError("You do not have permission to delete this delay record")
        
    # 3. Targeted deletion
    rows_affected = repo_delete_delay(delay_id)
    if rows_affected == 0:
        current_app.logger.error("Failed to delete delay %s despite previous check", delay_id)
        raise RuntimeError("Deletion failed in database")

    log_activity(user_id, "DELETE_DELAY", f"Deleted delay record ID: {delay_id}")
    return True
