"""
Deterministic task completion calculations.

Separated from scoring_engine.py because these concern task lifecycle
state, not excuse authenticity. Both modules may be imported independently.
"""

import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

_DATETIME_FORMATS = (
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%dT%H:%M:%S",
    "%Y-%m-%d",
)


def _parse_datetime(value) -> datetime | None:
    """
    Coerce a string or datetime to a naive datetime.

    Returns None if parsing fails so callers can decide how to handle
    the gap rather than receiving a silent timedelta(0).
    """
    if isinstance(value, datetime):
        return value.replace(tzinfo=None) if value.tzinfo else value

    if isinstance(value, str):
        for fmt in _DATETIME_FORMATS:
            try:
                return datetime.strptime(value, fmt)
            except ValueError:
                continue
        logger.warning("_parse_datetime: could not parse %r", value)

    return None


def calculate_elapsed_time(created_at) -> timedelta:
    """
    Return elapsed time from creation to now.

    This single-argument form is what the dashboard and tasks routes call.
    Returns timedelta(0) if created_at cannot be parsed.
    """
    parsed = _parse_datetime(created_at)
    if parsed is None:
        return timedelta(0)
    # Using now() to match existing logic which might not be using UTC consistently
    return datetime.now() - parsed


def calculate_elapsed_between(created_at, completion_time) -> timedelta:
    """
    Return elapsed time between two timestamps.

    Used when the completion timestamp is known (e.g. for scoring
    completed tasks). Returns timedelta(0) if either value is unparseable.
    """
    start = _parse_datetime(created_at)
    end   = _parse_datetime(completion_time)
    if start is None or end is None:
        return timedelta(0)
    return end - start


def calculate_delay_duration(elapsed_minutes: int, estimated_minutes: int) -> int:
    """Return how many minutes over the estimate a task ran (0 if on time)."""
    return max(elapsed_minutes - estimated_minutes, 0)


def is_task_delayed(elapsed_minutes: int, estimated_minutes: int) -> bool:
    """Return True if the task took longer than estimated."""
    return elapsed_minutes > estimated_minutes


def calculate_task_status(elapsed_minutes: int, estimated_minutes: int) -> str:
    """Return 'Completed' (normalized for DB status)."""
    return "Completed"


def calculate_efficiency_score(total_tasks: int, rationalizations: int) -> float:
    """
    Mathematical backend for the Efficiency Gauge.
    Formula: Efficiency% = (1 - Total Rationalizations / Total Tasks) * 100
    """
    if total_tasks == 0:
        return 100.0
    score = (1 - (rationalizations / total_tasks)) * 100
    return round(max(0, min(score, 100)), 2)
