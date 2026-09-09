"""
report_service.py
=================
Assembles structured data dictionaries for the AI Delay Analysis Report feature.

Public API:
    build_task_report_data(task_id, current_user_id, current_role)
    build_user_report_data(user_id, current_user_id, current_role)
"""

import json
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Report ID
# ---------------------------------------------------------------------------

def _generate_report_id(user_id: int, task_id: int | None = None) -> str:
    """
    Format: EPAI-YYMMDD-HHMMxM-U{user_id}-T{task_id}
    Example: EPAI-260303-1037AM-U17-T45
    """
    now = datetime.now()
    date_part = now.strftime("%y%m%d")
    time_part = now.strftime("%I%M%p")   # e.g. 1037AM
    task_part = f"-T{task_id}" if task_id else ""
    return f"EPAI-{date_part}-{time_part}-U{user_id}{task_part}"


def _format_generated_on() -> str:
    """Human-readable timestamp: 03 March 2026, 10:37 AM"""
    return datetime.now().strftime("%d %B %Y, %I:%M %p")


# ---------------------------------------------------------------------------
# Groq AI Conclusion
# ---------------------------------------------------------------------------

_REPORT_SYSTEM_PROMPT = (
    "You are an expert HR analyst. "
    "Generate 4-6 short, punchy, and catchy bullet points evaluating the employee's delay metrics. "
    "Each bullet point should be on a new line starting with '• '. "
    "Use strong verbs and keep each point under 12 words. "
    "Focus on immediate takeaways. Return ONLY the bullet points."
)


def _split_to_points(text: str) -> list[str]:
    """Split a conclusion string into individual bullet points."""
    import re
    # Try splitting by bullet markers first
    parts = re.split(r'[•\-\*]\s*', text)
    points = [p.strip() for p in parts if p.strip()]
    if len(points) >= 2:
        return points
    # Fall back to splitting by sentences
    sentences = re.split(r'(?<=[.!?])\s+', text.strip())
    return [s.strip() for s in sentences if s.strip()]


def _generate_ai_conclusion(
    total_delays: int,
    common_category: str,
    avg_sentiment: float,
    risk_score: float,
    user_name: str = "the employee",
) -> str:
    """Call Groq to produce the AI conclusion paragraph. Falls back gracefully."""
    try:
        from services.ai_service import get_ai_response
        prompt = (
            f"Employee Delay Summary for {user_name}:\n"
            f"Total Delays: {total_delays}\n"
            f"Most Frequent Delay Category: {common_category}\n"
            f"Average Sentiment Polarity: {round(avg_sentiment, 2)}\n"
            f"Overall Risk Score: {round(risk_score, 1)}%\n\n"
            "Generate 4-6 short, catchy evaluation bullet points. "
            "Each point under 12 words. Kick off with '• '."
        )
        result = get_ai_response(prompt, system_instruction=None)
        if result and result.strip() and result != "AI unavailable.":
            return result.strip()
    except Exception as e:
        logger.warning("Groq conclusion generation failed: %s", e)

    # Deterministic fallback
    risk_label = "high" if risk_score > 70 else ("moderate" if risk_score > 40 else "low")
    return (
        f"• {user_name} has recorded {total_delays} delay(s), predominantly attributed to "
        f"\"{common_category}\" patterns.\n"
        f"• Behavioral analysis indicates a {risk_label} risk profile "
        f"with an average sentiment polarity of {round(avg_sentiment, 2):.2f}.\n"
        f"• Further monitoring is recommended to validate improvement trends.\n"
        f"• Overall risk score stands at {round(risk_score, 1)}%, reflecting current performance metrics."
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_analysis(delay: dict) -> dict:
    """Safely extract the ai_analysis_json snapshot as a dict."""
    if not delay: return {}
    raw = delay.get("ai_analysis_json") or delay.get("ai_analysis")
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, dict): return parsed
        except Exception:
            pass
    return {}


def _access_check(current_user_id: int, current_role: str, target_user_id: int, task=None):
    """
    Raise PermissionError if the caller is not authorised.
    Rules:
      - admin/manager → always allowed
      - employee → only if they are the task's assignee (for task reports)
                   or the target_user_id equals their own id (for user reports)
    """
    if current_role in ("admin", "manager"):
        return
    if task:
        if task.get("assigned_to") != current_user_id:
            raise PermissionError("You do not have permission to view this report.")
    else:
        if target_user_id != current_user_id:
            raise PermissionError("You do not have permission to view this report.")


# ---------------------------------------------------------------------------
# Single-Task Report
# ---------------------------------------------------------------------------

def build_task_report_data(task_id: int, current_user_id: int, current_role: str) -> dict:
    """
    Assembles the complete data dict for a single-task report.

    Raises:
        LookupError  — task not found
        PermissionError — caller not authorised
    """
    from repository.tasks_repo import get_task_by_id
    from repository.users_repo import get_user_by_id
    from repository.delays_repo import get_delays_by_task

    # --- Task ---
    task = get_task_by_id(task_id)
    if not task:
        raise LookupError(f"Task {task_id} not found.")

    _access_check(current_user_id, current_role, task.get("assigned_to"), task=task)

    # --- User (assignee) ---
    user = get_user_by_id(task.get("assigned_to")) or {}

    # --- Delay (most recent) ---
    delays = get_delays_by_task(task_id) or []
    delay_record = delays[0] if delays else None
    analysis = _parse_analysis(delay_record) if delay_record else {}

    delay_section: dict = {}
    document_section: dict | None = None
    scores_section: dict = {}

    if delay_record:
        # The snapshot 'analysis' may have 'verdict' as a string or a dict
        v_raw = analysis.get("verdict", "UNKNOWN")
        if isinstance(v_raw, dict):
            v_label = v_raw.get("verdict", "UNKNOWN")
            v_score = v_raw.get("fake_score", 0)
            v_reason = v_raw.get("verdict_reason", "")
        else:
            v_label = str(v_raw)
            v_score = analysis.get("authenticity_score", 0) # Fallback
            v_reason = ""

        s_raw = analysis.get("sentiment", {})
        if isinstance(s_raw, dict):
            s_pol = s_raw.get("polarity", 0)
            s_lbl = s_raw.get("assessment", "N/A")
        else:
            s_pol = 0
            s_lbl = str(s_raw)

        delay_section = {
            "delay_days":   delay_record.get("delay_duration", 0),
            "reason_text":  delay_record.get("reason_text", ""),
            "category":     analysis.get("excuse_category", analysis.get("category", "Unknown")),
            "confidence":   round(analysis.get("confidence", 0), 1),
            "sentiment_polarity":    round(s_pol, 2),
            "sentiment_label":       s_lbl,
            "verdict":               v_label,
            "fake_score":            v_score,
            "verdict_reason":        v_reason,
            "submitted_at":          delay_record.get("submitted_at"),
        }

        scores_section = {
            "authenticity":      delay_record.get("score_authenticity", 0),
            "avoidance":         delay_record.get("score_avoidance", 0),
            "risk_level":        delay_record.get("risk_level", "Unknown"),
            "pattern_frequency": analysis.get("pattern_frequency", len(delays)),
            "reliability_index": analysis.get("reliability_index", 0),
            "risk_score":        analysis.get("risk_score", delay_record.get("score_avoidance", 0)),
        }

        # Proof document
        proof_path = delay_record.get("proof_path")
        if proof_path:
            filename = proof_path.split("/")[-1]
            ext = filename.rsplit(".", 1)[-1].upper() if "." in filename else "FILE"
            document_section = {
                "name":        filename,
                "file_type":   ext,
                "uploaded_at": delay_record.get("submitted_at"),
                "path":        proof_path,
            }

    # --- AI Conclusion ---
    avg_sentiment = delay_section.get("sentiment_polarity", 0) if delay_section else 0
    risk_score    = scores_section.get("risk_score", 0) if scores_section else 0
    conclusion    = _generate_ai_conclusion(
        total_delays   = len(delays),
        common_category= delay_section.get("category", "N/A") if delay_section else "N/A",
        avg_sentiment  = avg_sentiment,
        risk_score     = risk_score,
        user_name      = user.get("full_name", "the employee"),
    )

    return {
        "report_id":    _generate_report_id(user.get("id", current_user_id), task_id),
        "generated_on": _format_generated_on(),
        "user": {
            "name":     user.get("full_name", "Unknown"),
            "email":    user.get("email", "Unknown"),
            "role":     user.get("role", "employee").capitalize(),
            "job_role": user.get("job_role") or "Not specified",
        },
        "task": {
            "id":           task_id,
            "title":        task.get("title", ""),
            "description":  task.get("description", ""),
            "priority":     task.get("priority", "Medium"),
            "complexity":   task.get("complexity", 1),
            "deadline":     task.get("deadline"),
            "status":       task.get("status", "Unknown"),
            "created_at":   task.get("created_at"),
            "completed_at": task.get("completed_at"),
        },
        "delay":      delay_section,
        "document":   document_section,
        "scores":     scores_section,
        "analysis":   analysis,
        "conclusion": conclusion,
        "conclusion_points": _split_to_points(conclusion),
        "has_delay":  bool(delay_record),
    }


# ---------------------------------------------------------------------------
# Consolidated User Report
# ---------------------------------------------------------------------------

def build_user_report_data(user_id: int, current_user_id: int, current_role: str) -> dict:
    """
    Assembles aggregated data for a consolidated user delay report.

    Raises:
        LookupError  — user not found
        PermissionError — caller not authorised
    """
    from repository.users_repo import get_user_by_id
    from repository.delays_repo import get_delays_by_user
    from repository.tasks_repo import get_tasks_by_user

    _access_check(current_user_id, current_role, user_id)

    user = get_user_by_id(user_id)
    if not user:
        raise LookupError(f"User {user_id} not found.")

    delays = get_delays_by_user(user_id) or []
    tasks  = get_tasks_by_user(user_id)  or []

    # --- Aggregate stats ---
    total_tasks  = len(tasks)
    total_delays = len(delays)

    # Category distribution
    categories = []
    sentiments = []
    risk_scores = []

    delay_rows = []
    for d in delays:
        snap = _parse_analysis(d)
        cat  = snap.get("excuse_category", snap.get("category", "Unknown"))
        conf = round(snap.get("confidence", 0), 1)
        categories.append(cat)

        sent_raw = snap.get("sentiment", {})
        if isinstance(sent_raw, dict):
            sent_val = sent_raw.get("polarity", 0)
        else:
            sent_val = 0
        sentiments.append(sent_val)

        risk_val = snap.get("risk_score")
        if risk_val is None:
            risk_val = d.get("score_avoidance", 0)
        risk_scores.append(risk_val)

        delay_rows.append({
            "task_title":  d.get("task_title", f"Task #{d.get('task_id', '?')}"),
            "delay_days":  d.get("delay_duration", 0),
            "category":    cat,
            "confidence":  conf,
            "risk_level":  d.get("risk_level", "Unknown"),
            "submitted_at": d.get("submitted_at"),
        })

    most_common_category = (
        max(set(categories), key=categories.count) if categories else "N/A"
    )
    avg_sentiment = round(sum(sentiments) / len(sentiments), 2) if sentiments else 0.0
    avg_risk      = round(sum(risk_scores) / len(risk_scores), 1) if risk_scores else 0.0
    delay_rate    = round((total_delays / total_tasks) * 100, 1) if total_tasks else 0.0

    conclusion = _generate_ai_conclusion(
        total_delays    = total_delays,
        common_category = most_common_category,
        avg_sentiment   = avg_sentiment,
        risk_score      = avg_risk,
        user_name       = user.get("full_name", "the employee"),
    )

    return {
        "report_id":    _generate_report_id(user_id),
        "generated_on": _format_generated_on(),
        "user": {
            "id":       user_id,
            "name":     user.get("full_name", "Unknown"),
            "email":    user.get("email", "Unknown"),
            "role":     user.get("role", "employee").capitalize(),
            "job_role": user.get("job_role") or "Not specified",
        },
        "stats": {
            "total_tasks":          total_tasks,
            "total_delays":         total_delays,
            "delay_rate":           delay_rate,
            "most_common_category": most_common_category,
            "avg_sentiment":        avg_sentiment,
            "avg_risk_score":       avg_risk,
        },
        "delay_rows": delay_rows,
        "conclusion": conclusion,
        "conclusion_points": _split_to_points(conclusion),
    }
