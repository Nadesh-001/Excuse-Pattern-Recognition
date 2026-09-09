from difflib import SequenceMatcher

COMMON_PHRASES = [
    "not feeling well",
    "network issue",
    "personal reason",
    "system problem",
    "unexpected issue"
]

PATTERN_PENALTIES = {
    "repeated_excuse": 10,
    "generic_phrase_reuse": 5,
    "late_submission_pattern": 8,
    "risk_escalation": 12,
    "deadline_edge_abuse": 6
}

def similarity(a: str, b: str) -> float:
    if not a or not b: return 0.0
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()

def detect_repeated_excuse(current_reason: str, past_reasons: list) -> bool:
    for old in past_reasons:
        if old and similarity(current_reason, old) > 0.85:
            return True
    return False

def detect_phrase_reuse(reason: str) -> list:
    hits = []
    if not reason: return hits
    text = reason.lower()
    for phrase in COMMON_PHRASES:
        if phrase in text:
            hits.append(phrase)
    return hits

def detect_late_submission_pattern(delays: list) -> bool:
    if not delays or len(delays) < 3:
        return False
        
    # Check if 'is_after_deadline' is present or infer from delay_duration
    late_count = 0
    for d in delays:
        is_late = d.get("is_after_deadline")
        if is_late is None:
             # Fallback: check delay_duration. If > 0, likely late.
             is_late = d.get("delay_duration", 0) > 0
        
        if is_late:
            late_count += 1
            
    return (late_count / len(delays)) > 0.7

def detect_risk_escalation(risk_levels: list) -> bool:
    if not risk_levels or len(risk_levels) < 2:
        return False
        
    score_map = {"Low": 1, "Medium": 2, "High": 3, "LOW": 1, "MEDIUM": 2, "HIGH": 3}
    
    # risk_levels is ordered NEWEST first typically if from get_user_delay_history
    # But for escalation check (trend over time), we want OLDEST -> NEWEST.
    # The caller provides risk_levels. We assume caller knows order. 
    # Usually repository returns DESC (Newest first).
    # So numeric[0] is newest. numeric[-1] is oldest.
    # Escalation: Oldest (Low) -> Newest (High).
    # So numeric should be INCREASING if we iterate Old -> New.
    # If list is New -> Old (repo standard), then numeric should be DECREASING (High -> Low).
    
    # Let's clarify. If we iterate New -> Old:
    # High (3), Medium (2), Low (1).
    # This is escalation over time.
    # So numeric[0] (New) > numeric[1] (Older).
    
    # Wait, the user logic example: "numeric == sorted(numeric)".
    # This implies numeric is [1, 2, 3] (sorted ascending).
    # If numeric represents time series T1, T2, T3.
    # Then T1=1, T2=2, T3=3.
    # If standard fetch is DESC order (T3, T2, T1), then numeric is [3, 2, 1].
    # Which is NOT sorted ascending.
    # So we need to REVERSE the list if it came from the repo (DESC).
    
    # We will assume input is DESC (Newest first).
    reversed_risks = risk_levels[::-1] # Now Oldest -> Newest
    
    numeric_chronological = [score_map.get(str(r), 1) for r in reversed_risks if r]
    
    if len(numeric_chronological) < 2: return False

    is_sorted = all(numeric_chronological[i] <= numeric_chronological[i+1] for i in range(len(numeric_chronological)-1))
    
    # Escalation condition: Strictly worse end state?
    # User: "numeric[-1] >= 2" (Medium or High at end).
    return is_sorted and numeric_chronological[-1] >= 2 and numeric_chronological[-1] > numeric_chronological[0]

def detect_deadline_edge_abuse(hours_left_list: list) -> bool:
    if not hours_left_list:
        return False
        
    # User logic: "edge cases = [h for h in hours_left_list if h <= 1]"
    # Assuming hours_left represents time BEFORE deadline. 
    # If late, hours_left might be negative?
    # Logic implies checking if users submit strictly close to deadline (0-1 hours left).
    valid_hours = [h for h in hours_left_list if h is not None]
    if not valid_hours: return False
    
    edge_cases = [h for h in valid_hours if 0 <= h <= 1]
    return (len(edge_cases) / len(valid_hours)) > 0.6

def run_pattern_detection(current_reason: str, history: list, hours_left_current: int, is_after_deadline_current: bool) -> list:
    """
    Run all pattern checks.
    history: List of delay dicts from DB (Newest first).
    """
    flags = []

    # Extract history data
    past_reasons = [d.get("reason_text", "") for d in history]
    risks = [d.get("risk_level", "Low") for d in history]
    
    # Compute historical hours_left
    # Repo now returns `submitted_at` and `deadline` (if joined).
    historical_hours_left = []
    for d in history:
        submitted = d.get("submitted_at")
        deadline = d.get("deadline") # might be None/NaT if no join or no deadline
        if submitted and deadline:
            try:
                # deadline might be date or datetime. submitted is datetime.
                # If deadline is date, convert to datetime eod? usually stored as datetime in schema?
                # Assume comparable.
                delta = deadline - submitted
                hours = delta.total_seconds() / 3600
                historical_hours_left.append(hours)
            except Exception as e:
                # Log the error but continue with other delays
                import logging
                logging.getLogger(__name__).debug("Error calculating hours left for delay: %s", e)
                historical_hours_left.append(None)
        else:
            historical_hours_left.append(None)
            
    # Add current to history analyses where appropriate
    # For repeated excuse: checks against past.
    if detect_repeated_excuse(current_reason, past_reasons):
        flags.append("repeated_excuse")

    # Phrase Reuse (current only)
    reused_phrases = detect_phrase_reuse(current_reason)
    if reused_phrases:
        flags.append("generic_phrase_reuse")

    # Late Submission (History + Current)
    # We need to create updated list representing "all submissions including this one"
    current_delay_sim = {"is_after_deadline": is_after_deadline_current}
    history_for_timing = [current_delay_sim] + history # Newest (Current) + Old 
    # detect_late checks iteration, order doesn't matter for count.
    if detect_late_submission_pattern(history_for_timing):
        flags.append("late_submission_pattern")

    # Risk Escalation (History risks).
    # Should include current risk? We don't have current risk yet! It's calculated AFTER score.
    # But patterns affect score -> affect risk. Circular dependency?
    # User prompt: "Risk Escalation Pattern ... detect worsening behavior".
    # Since this penalizes score, we check PAST trend.
    # Current risk depends on this penalty.
    if detect_risk_escalation(risks):
        flags.append("risk_escalation")

    # Deadline Edge Abuse (History + Current)
    all_hours = [hours_left_current] + historical_hours_left
    if detect_deadline_edge_abuse(all_hours):
        flags.append("deadline_edge_abuse")

    return flags

def apply_pattern_penalty(score: int, flags: list) -> int:
    penalty = 0
    for f in flags:
        penalty += PATTERN_PENALTIES.get(f, 0)
    return max(score - penalty, 0)
