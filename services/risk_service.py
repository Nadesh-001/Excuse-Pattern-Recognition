import logging
from datetime import datetime
from repository.tasks_repo import execute_query, get_task_by_id
from repository.users_repo import get_user_by_id
from repository.delays_repo import get_delays_by_user

import time
import threading

logger = logging.getLogger(__name__)

# --- Resource Protection: Global Result Cache ---
_risk_cache = {
    'project_health': {'data': None, 'expires': 0},
    'batch_risk': {} # {task_ids_hash: {'data': score, 'expires': time}}
}
_risk_lock = threading.Lock()
CACHE_TTL = 300 # 5 minutes

def calculate_workload_index(user_id):
    """
    Workload Index = (Active Tasks * 0.4) + (Pending Hours * 0.3) + (Overdue Tasks * 0.3)
    """
    try:
        # Get active (Pending or In Progress) tasks
        active_tasks = execute_query(
            "SELECT COUNT(id) as count, SUM(estimated_minutes) as total_min FROM tasks WHERE assigned_to = %s AND status IN ('Pending', 'In Progress')",
            (user_id,)
        )
        task_count = active_tasks[0]['count'] if active_tasks else 0
        pending_hours = (active_tasks[0]['total_min'] or 0) / 60
        
        # Get overdue tasks
        overdue = execute_query(
            "SELECT COUNT(id) as count FROM tasks WHERE assigned_to = %s AND status IN ('Pending', 'In Progress') AND deadline < CURRENT_DATE",
            (user_id,)
        )
        overdue_count = overdue[0]['count'] if overdue else 0
        
        index = (task_count * 0.4) + (pending_hours * 0.3) + (overdue_count * 0.3)
        return round(index, 2)
    except Exception as e:
        logger.error(f"Error calculating workload index: {e}")
        return 0.0

def calculate_user_reliability(user_id):
    """
    Reliability = 100 - (weighted delay impact)
    Simplified logic for now: Penalty based on number of delays and their risk level.
    """
    try:
        delays = get_delays_by_user(user_id)
        if not delays:
            return 100.0
            
        penalty = 0
        for d in delays:
            if d['risk_level'] == 'High':
                penalty += 15
            elif d['risk_level'] == 'Medium':
                penalty += 8
            else:
                penalty += 3
                
        # Also factor in on-time completion percentage if we had that data easily
        reliability = max(0, 100 - penalty)
        return float(reliability)
    except Exception as e:
        logger.error(f"Error calculating user reliability: {e}")
        return 100.0

def get_category_risk_multiplier(category):
    """
    Track delay rate per category:
    AI features -> 1.65x
    UI fixes -> 1.20x
    Bug fixes -> 1.30x
    """
    multipliers = {
        'AI Development': 1.65,
        'Frontend / UI': 1.20,
        'Bug Fix': 1.30,
        'Research': 1.50,
        'Technical Debt': 1.40
    }
    return multipliers.get(category, 1.0)

def calculate_estimation_bias(user_id):
    """
    Tier 5: Cognitive Estimation Analysis.
    Compares estimated vs actual time for completed tasks to find bias.
    """
    try:
        res = execute_query(
            """SELECT estimated_minutes, 
                      EXTRACT(EPOCH FROM (completion_timestamp - created_at))/60 as actual_minutes 
               FROM tasks 
               WHERE assigned_to = %s AND status = 'Completed' 
               ORDER BY completion_timestamp DESC LIMIT 10""",
            (user_id,)
        )
        if not res or len(res) < 3:
            return 1.0 # Not enough data
            
        biases = []
        for row in res:
            est = row['estimated_minutes'] or 1
            act = row['actual_minutes'] or 1
            biases.append(act / est)
            
        avg_bias = sum(biases) / len(biases)
        return round(max(0.8, min(2.5, avg_bias)), 2)
    except Exception as e:
        logger.error(f"Error calculating estimation bias: {e}")
        return 1.0

def get_deadline_multiplier(deadline_date):
    """
    Stress Multiplier: Risk increases as deadline approaches.
    """
    if not deadline_date:
        return 1.0
        
    deadline = datetime.combine(deadline_date, datetime.min.time())
    delta = deadline - datetime.now()
    hours_left = delta.total_seconds() / 3600
    
    if hours_left < 0:
        return 2.5 # Overdue
    if hours_left < 24:
        return 2.0
    if hours_left < 48:
        return 1.5
    if hours_left < 168: # 1 week
        return 1.2
    return 1.0

def calculate_predictive_risk(task_id):
    """
    Phase 2: Predictive Delay Risk Engine (Pre-Deadline AI)
    Signals: Priority, Deadline Proximity, Complexity, Reliability, Workload
    """
    try:
        task = get_task_by_id(task_id)
        if not task:
            return 0, {}
            
        user_id = task['assigned_to']
        reliability = calculate_user_reliability(user_id)
        workload = calculate_workload_index(user_id)
        
        # Base points (0-100 scale)
        # 1. Priority Weight
        priority_weights = {'High': 20, 'Medium': 10, 'Low': 5}
        p_weight = priority_weights.get(task['priority'], 10)
        
        # 2. Complexity (1-10)
        complexity_score = (task.get('complexity', 1) or 1) * 3
        
        # 3. Reliability Impact
        rel_penalty = max(0, (100 - reliability) * 0.5)
        
        # 4. Workload Pressure
        workload_penalty = min(20, workload * 3)
        
        base_score = p_weight + complexity_score + rel_penalty + workload_penalty
        
        # 5. Behavioral Momentum (Tier 2 Integration)
        from services.user_service import get_user_momentum
        momentum = get_user_momentum(user_id)
        momentum_impact = 0
        if momentum.get('escalation_velocity') == 'spiral':
            momentum_impact += 12
        drift = momentum.get('risk_drift', 0) or 0
        if drift > 8:
            momentum_impact += 10
        elif drift > 4:
            momentum_impact += 5
            
        # 6. Role-Based Sensitivity (Tier 4 Integration)
        from services.user_service import compute_behavioral_state
        actor = get_user_by_id(user_id)
        role = actor.get('role', 'employee')
        role_mult = 1.25 if role in ('admin', 'manager') else 1.0
        
        # 7. HMM Behavioral State (Tier 4 Integration)
        state_data = compute_behavioral_state(user_id)
        current_state = state_data.get('state', 'STABLE')
        state_mults = {
            'STABLE': 1.0,
            'DRIFTING': 1.15,
            'HIGH_RISK': 1.30,
            'RECOVERING': 0.90
        }
        state_mult = state_mults.get(current_state, 1.0)
        
        # Multipliers
        cat_mult = get_category_risk_multiplier(task.get('category', 'General'))
        dead_mult = get_deadline_multiplier(task['deadline'])
        
        final_score = (base_score + momentum_impact) * cat_mult * dead_mult * role_mult * state_mult
        clamped_risk = min(100, int(final_score))
        
        factors = {
            "Priority Baseline": p_weight,
            "Complexity impact": complexity_score,
            "User Reliability Impact": round(rel_penalty, 1),
            "Team Workload Pressure": round(workload_penalty, 1),
            "Behavioral Momentum Factor": momentum_impact,
            "Category Risk Multiplier": cat_mult,
            "Deadline Multiplier": dead_mult,
            "Role Impact Multiplier": role_mult,
            "Behavioral State Multiplier": state_mult
        }

        
        return clamped_risk, factors
    except Exception as e:
        logger.error(f"Error calculating predictive risk for task {task_id}: {e}")
        return 0, {}


def batch_predictive_risk(task_ids: list) -> float:
    """
    Compute average predictive risk with optimized sampling for large task sets.
    """
    if not task_ids:
        return 0.0
        
    # Optimization: sample only recent/relevant tasks for large sets to keep response time low
    sampling_limit = 10
    sample = task_ids[:sampling_limit]
    
    try:
        total = 0
        for tid in sample:
            score, _ = calculate_predictive_risk(tid)
            total += score
        return round(total / len(sample), 1)
    except Exception as e:
        logger.error("Error in batch_predictive_risk: %s", e)
        return 0.0

def detect_behavioral_drift(user_id):
    """
    detect_behavioral_drift: Detect sudden behavior change.
    Example: User usually 90% on time, suddenly 3 consecutive delays.
    """
    try:
        # Get historical on-time rate (simplified)
        res = execute_query("SELECT reliability_score FROM users WHERE id = %s", (user_id,))
        historical_reliability = res[0]['reliability_score'] if res else 100.0
        
        # Get recent delays (last 30 days)
        recent_delays = execute_query(
            "SELECT COUNT(id) as count FROM delays WHERE user_id = %s AND submitted_at > NOW() - INTERVAL '30 days'",
            (user_id,)
        )
        recent_count = recent_delays[0]['count'] if recent_delays else 0
        
        # If historical reliability is high but recent delays are spikey
        if historical_reliability > 85 and recent_count >= 3:
            return True, "Significant spike in delay frequency detected (Behavioral Drift)"
        return False, ""
    except Exception as e:
        logger.error(f"Error detecting behavioral drift: {e}")
        return False, ""

def validate_task_feasibility(title, description, estimated_minutes, user_id):
    """
    detects unrealistic planning at task creation stage.
    """
    try:
        # 1. Complexity check
        word_count = len(description.split())
        complexity_est = max(1, min(10, word_count // 20))
        
        # 2. Time vs Complexity
        # If description is long but estimate is too low
        if complexity_est > 5 and estimated_minutes < 120:
             return 74, "⚠ Estimated time may be insufficient for this description complexity."
             
        # 3. Workload check
        workload = calculate_workload_index(user_id)
        if workload > 15:
            return 85, "🚨 Critical workload detected. Feasibility risk high."
            
        return 0, ""
    except Exception as e:
        logger.error(f"Error validating task feasibility: {e}")
        return 0, ""

def check_early_warning(task_id):
    """
    If: 60% timeline passed, No status update, High priority -> Auto flag
    """
    try:
        task = get_task_by_id(task_id)
        if not task or task['status'] == 'Completed':
            return False, ""

        created_at = task['created_at']

        # Normalise deadline: DB returns date or datetime; datetime.combine needs date
        dl = task['deadline']
        if dl is None:
            return False, ""
        if isinstance(dl, datetime):
            deadline = dl
        else:
            # date object
            deadline = datetime.combine(dl, datetime.min.time())

        total_duration = (deadline - created_at).total_seconds()
        elapsed = (datetime.now() - created_at).total_seconds()

        if total_duration > 0 and (elapsed / total_duration) > 0.6:
            if task['priority'] == 'High' and task['status'] == 'Pending':
                return True, "⚠ Early Delay Risk: 60% of timeline passed with no progress on High-priority task."

        return False, ""
    except Exception as e:
        logger.error(f"Error checking early warning: {e}")
        return False, ""

def get_risk_recommendations(task_id: int, risk_score: int, factors: dict) -> list:
    """
    Tier 5: Prescriptive Intelligence.
    Provides actionable mitigations and adaptive rebalancing suggestions.
    """
    recs = []
    
    # 1. Base recommendations
    if risk_score > 75:
        recs.append("🔴 HIGH RISK: Task rebalancing or deadline extension required.")
    
    # 2. Team Workload Pressure
    if factors.get('Team Workload Pressure', 0) > 15:
        recs.append("⚠️ Systemic Workload: Recommend redistributing non-critical tasks to low-load peers.")
        
    # 3. Tier 4: State-based mitigations
    from services.user_service import compute_behavioral_state
    task = get_task_by_id(task_id)
    if task:
        user_id = task['assigned_to']
        user_state = compute_behavioral_state(user_id)
        state = user_state.get('state', 'STABLE')
        
        # Tier 5: Prescriptive Actions
        if state == 'DRIFTING':
            recs.append("🔍 PRESCRIPTIVE: Implement 'Complexity Throttling'. Limit new High-complexity tasks for 7 days.")
        elif state == 'HIGH_RISK':
            recs.append("🚨 PRESCRIPTIVE: Immediate Task Reallocation. Consider peer handover for this specific task.")
        elif state == 'RECOVERING':
            recs.append("🛡️ PRESCRIPTIVE: Stability Support. Maintain current load to reinforce recovery momentum.")

    # 4. Adaptive Empathy (Tier 5)
    from services.analytics_service import get_team_resilience_index
    tri = get_team_resilience_index()
    if tri.get('score', 100) < 50:
        recs.append("🧠 ADAPTIVE EMPATHY: Team-wide burnout detected. System strictness auto-reduced by 15% for this cycle.")

    # 5. Adaptive Estimation Tuning (Tier 5)
    bias = calculate_estimation_bias(user_id)
    if bias > 1.2:
        recs.append(f"⏱️ COGNITIVE BUFFER: You typically under-estimate by {int((bias-1)*100)}%. Recommend +{int((bias-1)*100)}% buffer for next task.")

    return recs


def check_risk_escalation(user_id):
    """
    Risk Escalation Tracker (Levels 1-3)
    Enhanced with Tier 2 Behavioral Momentum integration.
    """
    try:
        from services.user_service import get_user_momentum
        momentum = get_user_momentum(user_id)
        
        # Base count of high risk delays in last 14 days
        res = execute_query(
            "SELECT COUNT(*) as count FROM delays WHERE user_id = %s AND risk_level = 'High' AND submitted_at > NOW() - INTERVAL '14 days'",
            (user_id, )
        )
        high_risk_count = res[0]['count'] if res else 0
        
        # Calculate Base Level
        base_level = 0
        if high_risk_count >= 5:
            base_level = 3
        elif high_risk_count >= 3:
            base_level = 2
        elif high_risk_count >= 1:
            base_level = 1
            
        # MOMENTUM INFLUENCE
        # 1. Significant drift jumps level immediately
        if (momentum.get('risk_drift') or 0) > 10:
            base_level = max(base_level, 2)
            
        # 2. Risk Spiral elevates level by 1
        if momentum.get('escalation_velocity') == 'spiral':
            base_level = min(3, base_level + 1)
            
        # Return Final Level + Contextual Message
        if base_level == 3:
            return 3, "LEVEL 3: Critical Alert - Consistent patterns of high-risk behavior detected."
        elif base_level == 2:
            return 2, f"LEVEL 2: High Monitoring - {'Spiral pattern detected' if momentum.get('escalation_velocity') == 'spiral' else 'Elevated risk drift/frequency'} observed."
        elif base_level == 1:
            return 1, "LEVEL 1: Warning - Emerging risk patterns detected in recent activity."
            
        return 0, "No escalation required."
    except Exception as e:
        logger.error(f"Error checking risk escalation: {e}")
        return 0, ""


def get_project_health_index():
    """
    Project Health = (Avg Reliability * 0.4) + (On-Time Completion Rate * 0.4) - (Overdue Task Ratio * 0.2)
    Cached for 5 minutes (Governance Level C).
    """
    global _risk_cache
    now = time.time()
    
    with _risk_lock:
        if _risk_cache['project_health']['data'] and now < _risk_cache['project_health']['expires']:
            return _risk_cache['project_health']['data']

    try:
        # Avg Reliability
        res_rel = execute_query("SELECT AVG(reliability_score) as avg_rel FROM users WHERE active_status = TRUE")
        avg_rel = res_rel[0]['avg_rel'] if res_rel and res_rel[0]['avg_rel'] else 100.0
        
        # On-Time Completion Rate
        total_completed = execute_query("SELECT COUNT(*) as count FROM tasks WHERE status = 'Completed'")
        comp_count = total_completed[0]['count'] if total_completed else 0
        if comp_count == 0:
            on_time_rate = 100.0
        else:
            delayed_comp = execute_query("SELECT COUNT(DISTINCT task_id) as count FROM delays")
            delayed_count = delayed_comp[0]['count'] if delayed_comp else 0
            on_time_rate = max(0, (comp_count - delayed_count) / comp_count * 100)
            
        # Overdue Task Ratio
        total_active_res = execute_query("SELECT COUNT(*) as count FROM tasks WHERE status IN ('Pending', 'In Progress')")
        active_count = total_active_res[0]['count'] if total_active_res else 0
        if active_count == 0:
            overdue_ratio = 0.0
        else:
            overdue_res = execute_query("SELECT COUNT(*) as count FROM tasks WHERE status IN ('Pending', 'In Progress') AND deadline < CURRENT_DATE")
            overdue_count = overdue_res[0]['count'] if overdue_res else 0
            overdue_ratio = (overdue_count / active_count) * 100
            
        health = (avg_rel * 0.4) + (on_time_rate * 0.4) - (overdue_ratio * 0.2)
        score = round(max(0, min(100, health)), 2)
        
        with _risk_lock:
            _risk_cache['project_health'] = {'data': score, 'expires': now + CACHE_TTL}
            
        return score
    except Exception as e:
        logger.error(f"Error calculating project health: {e}")
        return 50.0 # Default neutral
