from datetime import datetime, date as _date
from utils.time_utils import calculate_elapsed_time

_DEADLINE_FMT  = '%Y-%m-%d'
_TIMESTAMP_FMT = '%Y-%m-%d %H:%M:%S'


def enrich_task(task: dict) -> dict:
    """
    Add display-layer fields to a task dict in-place.

    Adds elapsed_time, status_badge, and badge_type.
    Safe to call multiple times (idempotent).
    """
    task['elapsed_time'] = calculate_elapsed_time(task.get('created_at'))
    
    # Calculate est_hours and est_minutes for display
    est_mins = task.get('estimated_minutes') or 0
    task['est_hours'] = est_mins // 60
    task['est_minutes'] = est_mins % 60
    
    # Ensure risk_score exists and is a number for the template
    task['risk_score'] = task.get('risk_score') or 0
    
    task['status_badge'], task['badge_type'] = _resolve_badge(task)
    return task


def _resolve_badge(task: dict) -> tuple[str, str]:
    status = task.get('status')
    if status == 'Completed':
        return _completion_badge(task)
    if status == 'Delayed':
        return 'Delayed', 'danger'
    return 'In Progress', 'info'


def _completion_badge(task: dict) -> tuple[str, str]:
    try:
        deadline_val = task['deadline']
        if isinstance(deadline_val, datetime):
            deadline_dt = deadline_val
        elif isinstance(deadline_val, _date):
            deadline_dt = datetime.combine(deadline_val, datetime.min.time())
        else:
            deadline_dt = datetime.strptime(str(deadline_val), _DEADLINE_FMT)

        comp_dt = task.get('completion_timestamp')
        if isinstance(comp_dt, str):
            comp_dt = datetime.strptime(comp_dt, _TIMESTAMP_FMT)
        if comp_dt is None:
            return 'Completed', 'success'
        if comp_dt.date() <= deadline_dt.date():
            return 'Completed on time', 'success'
        return 'Completed over time', 'warning'
    except (ValueError, TypeError, KeyError):
        return 'Completed', 'success'
