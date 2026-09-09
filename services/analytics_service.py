"""
Analytics Service — fetches, aggregates, and enriches analytics data.
"""
import logging
import re
import json
import math
import time
from datetime import datetime, timezone
from typing import Dict, List, Any
from collections import Counter
from repository.db import execute_query

logger = logging.getLogger(__name__)

from utils.async_workers import BackgroundProcessor


# Avoid top-level heavy imports to reduce OOM risk on Free Tier
# from services.intelligence_engine import (...)
# from services.nlp_service import (...)


# ---------------------------------------------------------------------------
# Fast Cache for Latency Mitigation (Free Tier Geography)
# ---------------------------------------------------------------------------
_ANALYTICS_FAST_CACHE = {} # {key: (data, expiry)}
_FAST_CACHE_TTL = 10      # seconds

def _get_cached(key):
    now = time.time()
    if key in _ANALYTICS_FAST_CACHE:
        data, expiry = _ANALYTICS_FAST_CACHE[key]
        if now < expiry:
            return data
    return None

def _set_cached(key, data):
    _ANALYTICS_FAST_CACHE[key] = (data, time.time() + _FAST_CACHE_TTL)


# ---------------------------------------------------------------------------
# AI integration (optional dependency)
# ---------------------------------------------------------------------------



AI_ENABLED = True

# --- ARCHITECTURE FREEZE v1.0 ---
MODEL_VERSION = "1.0"
WEIGHT_SCHEMA_VERSION = "1.0"
DECAY_LAMBDA = 0.9
NORMALIZATION_VERSION = "1.0"
# --------------------------------

# --------------------------------
# Stable Data Contracts
# --------------------------------

def _empty_ai_schema():
    """Return a stable dictionary shape to prevent Jinja UndefinedError."""
    return {
        "wrs_score": 0,
        "peer_comparison": {
            "percentile": 0,
            "z_score": 0.0,
            "label": "INSUFFICIENT_DATA",
            "population_mean": 0
        },
        "ai": {
            "behavioral_intelligence_score": 0,
            "confidence": {"score": 0, "label": "LOW"},
            "trust_volatility": {"volatility_score": 0},
            "explainability": {
                "auth_component": 0,
                "risk_component": 0,
                "delay_penalty": 0
            }
        },
        "ai_insights": [],
        "executive_summary": "Insufficient data for neural analysis.",
        "v1_intelligence": {
            "recommendations": [],
            "rolling_avg_risk": 0,
            "kinematics": {
                "risk_velocity": 0,
                "risk_acceleration": 0,
                "confidence": "LOW"
            },
            "integrity_index": {
                "score": 0,
                "status": "SECURE"
            }
        },
        "behavioral_state": {"state": "INITIALIZING"},
        "team_resilience": {"score": 100, "label": "CALIBRATING"}
    }

def _merge_with_schema(data: dict) -> dict:
    """Normalizes and merges data with the stable schema to prevent template crashes."""
    base = _empty_ai_schema()
    if not data:
        return base
    
    # Handle case where summary_json might be a string (JSONB vs JSON behavior)
    if isinstance(data, str):
        try:
            data = json.loads(data)
        except:
            return base

    # Explicitly merge key sections
    base.update({k: v for k, v in data.items() if k in base and k != "ai"})
    if "ai" in data and isinstance(data["ai"], dict):
        base["ai"].update(data["ai"])
    
    return base

def calculate_time_decay_score(delay_records: list[dict]) -> dict:
    """
    Calculate a time-decayed trust score where recent behavior matters more.
    """
    if not delay_records:
        return {"score": 100, "weighted_trust_score": 100}

    total_weight = 0
    weighted_sum = 0
    
    # Assume records are sorted desc (newest first)
    # Simple decay: 1.0, 0.9, 0.8...
    decay = 1.0
    decay_rate = 0.9
    
    for record in delay_records[:10]: # Look at last 10
        score = float(record.get('authenticity', 0))
        weighted_sum += score * decay
        total_weight += decay
        decay *= decay_rate
        
    final_score = round(weighted_sum / total_weight, 1) if total_weight > 0 else 0
    return {
        "score": final_score,
        "weighted_trust_score": final_score
    }


# ---------------------------------------------------------------------------
# SQL queries — one pair (user / team) per logical concern.
# Never constructed via string replacement at runtime.
# ---------------------------------------------------------------------------

# -- Aggregated stats --

_STATS_USER = """
WITH user_tasks AS (
    SELECT COUNT(id) AS total_tasks FROM tasks WHERE assigned_to = %s
),
user_delays AS (
    SELECT
        COUNT(id)                                               AS total_delays,
        COUNT(DISTINCT task_id)                                 AS unique_delayed_tasks,
        COALESCE(AVG(score_authenticity), 0)                   AS avg_auth,
        COALESCE(AVG(score_avoidance), 0)                      AS avg_avoid,
        COUNT(CASE WHEN risk_level = 'Low'    THEN 1 END)      AS risk_low,
        COUNT(CASE WHEN risk_level = 'Medium' THEN 1 END)      AS risk_med,
        COUNT(CASE WHEN risk_level = 'High'   THEN 1 END)      AS risk_high
    FROM delays WHERE user_id = %s
)
SELECT ut.total_tasks, ud.total_delays, ud.unique_delayed_tasks,
       ud.avg_auth, ud.avg_avoid, ud.risk_low, ud.risk_med, ud.risk_high
FROM user_tasks ut CROSS JOIN user_delays ud;
"""

_STATS_TEAM = """
WITH team_tasks AS (
    SELECT COUNT(id) AS total_tasks FROM tasks
),
team_delays AS (
    SELECT
        COUNT(id)                                               AS total_delays,
        COUNT(DISTINCT task_id)                                 AS unique_delayed_tasks,
        COALESCE(AVG(score_authenticity), 0)                   AS avg_auth,
        COALESCE(AVG(score_avoidance), 0)                      AS avg_avoid,
        COUNT(CASE WHEN risk_level = 'Low'    THEN 1 END)      AS risk_low,
        COUNT(CASE WHEN risk_level = 'Medium' THEN 1 END)      AS risk_med,
        COUNT(CASE WHEN risk_level = 'High'   THEN 1 END)      AS risk_high
    FROM delays
)
SELECT tt.total_tasks, td.total_delays, td.unique_delayed_tasks,
       td.avg_auth, td.avg_avoid, td.risk_low, td.risk_med, td.risk_high
FROM team_tasks tt CROSS JOIN team_delays td;
"""

# -- Day-of-week trend --

_TREND_USER = """
SELECT TO_CHAR(submitted_at, 'Dy') AS day_name,
       EXTRACT(DOW FROM submitted_at) AS day_idx,
       COUNT(*) AS count
FROM delays WHERE user_id = %s
GROUP BY day_name, day_idx ORDER BY day_idx;
"""

_TREND_TEAM = """
SELECT TO_CHAR(submitted_at, 'Dy') AS day_name,
       EXTRACT(DOW FROM submitted_at) AS day_idx,
       COUNT(*) AS count
FROM delays
GROUP BY day_name, day_idx ORDER BY day_idx;
"""

# -- Reason categories --

_WEATHER_KEYWORDS  = ['%%rain%%','%%storm%%','%%weather%%','%%flood%%','%%snow%%','%%temp%%','%%climate%%']
_HEALTH_KEYWORDS   = ['%%sick%%','%%ill%%','%%doctor%%','%%fever%%','%%appointment%%','%%health%%','%%injury%%']
_LABOR_KEYWORDS    = ['%%labor%%','%%staff%%','%%worker%%','%%shortage%%','%%absent%%','%%crew%%','%%team%%']
_MATERIAL_KEYWORDS = ['%%material%%','%%supply%%','%%delivery%%','%%stock%%','%%part%%','%%inventory%%','%%order%%']
_ALL_KEYWORDS      = _WEATHER_KEYWORDS + _HEALTH_KEYWORDS + _LABOR_KEYWORDS + _MATERIAL_KEYWORDS

def _build_category_query(where_clause: str) -> str:
    all_kw = ", ".join(f"'{k}'" for k in _ALL_KEYWORDS)
    w  = ", ".join(f"'{k}'" for k in _WEATHER_KEYWORDS)
    h  = ", ".join(f"'{k}'" for k in _HEALTH_KEYWORDS)
    l  = ", ".join(f"'{k}'" for k in _LABOR_KEYWORDS)
    m  = ", ".join(f"'{k}'" for k in _MATERIAL_KEYWORDS)
    return f"""
    SELECT
        COUNT(CASE WHEN reason_text ILIKE ANY(ARRAY[{w}])  THEN 1 END) AS "Weather",
        COUNT(CASE WHEN reason_text ILIKE ANY(ARRAY[{h}])  THEN 1 END) AS "Sickness",
        COUNT(CASE WHEN reason_text ILIKE ANY(ARRAY[{l}])  THEN 1 END) AS "Labor",
        COUNT(CASE WHEN reason_text ILIKE ANY(ARRAY[{m}])  THEN 1 END) AS "Material",
        COUNT(CASE WHEN reason_text NOT ILIKE ALL(ARRAY[{all_kw}]) THEN 1 END) AS "Other"
    FROM delays {where_clause};
    """

_CATEGORY_USER = _build_category_query("WHERE user_id = %s")
_CATEGORY_TEAM = _build_category_query("")

# -- Trust trend (time series) --

# -- Trend Queries --
_TRUST_TREND_USER = """
SELECT COALESCE(d.date, t.date) AS date,
       COALESCE(d.avg_auth, 75) AS avg_authenticity,
       COALESCE(d.avg_avoid, 25) AS avg_avoidance
FROM (
    SELECT created_at::date AS date FROM tasks WHERE assigned_to = %s
) t
LEFT JOIN (
    SELECT submitted_at::date AS date,
           AVG(score_authenticity) AS avg_auth,
           AVG(score_avoidance) AS avg_avoid
    FROM delays WHERE user_id = %s
    GROUP BY date
) d ON t.date = d.date
ORDER BY date DESC LIMIT 30;
"""

_TRUST_TREND_TEAM = """
SELECT COALESCE(d.date, t.date) AS date,
       COALESCE(d.avg_auth, 75) AS avg_authenticity,
       COALESCE(d.avg_avoid, 25) AS avg_avoidance
FROM (
    SELECT created_at::date AS date FROM tasks
) t
LEFT JOIN (
    SELECT submitted_at::date AS date,
           AVG(score_authenticity) AS avg_auth,
           AVG(score_avoidance) AS avg_avoid
    FROM delays
    GROUP BY date
) d ON t.date = d.date
ORDER BY date DESC LIMIT 30;
"""

# -- Excuse texts for NLP --

_EXCUSE_TEXTS_USER = """
SELECT reason_text, score_authenticity
FROM delays WHERE user_id = %s AND reason_text IS NOT NULL
ORDER BY submitted_at DESC LIMIT 20;
"""

_EXCUSE_TEXTS_TEAM = """
SELECT reason_text, score_authenticity
FROM delays WHERE reason_text IS NOT NULL
ORDER BY submitted_at DESC LIMIT 20;
"""

# -- Delay records for time-decay --

_DELAY_RECORDS_USER = """
SELECT score_authenticity AS authenticity, submitted_at
FROM delays WHERE user_id = %s
ORDER BY submitted_at DESC LIMIT 30;
"""

_DELAY_RECORDS_TEAM = """
SELECT score_authenticity AS authenticity, submitted_at
FROM delays ORDER BY submitted_at DESC LIMIT 30;
"""

_RATIONALIZATION_COUNT_USER = """
SELECT COUNT(*) as count FROM delays WHERE user_id = %s AND risk_level = 'High';
"""

_RATIONALIZATION_COUNT_TEAM = """
SELECT COUNT(*) as count FROM delays WHERE risk_level = 'High';
"""


# ---------------------------------------------------------------------------
# Query helpers — thin wrappers that pick the right query + params.
# ---------------------------------------------------------------------------

def _q(user_query, team_query, is_team: bool, user_id):
    """Execute the appropriate query variant and return rows."""
    if is_team:
        return execute_query(team_query, ()) or []
    
    # Use regex to count only REAL %s placeholders (not %%s which are escaped % signs)
    # e.g. %%sick%% contains '%s' as substring but it's part of a LIKE pattern, not a param slot
    import re
    param_count = len(re.findall(r'(?<!%)%s', user_query))
    params = (user_id,) * param_count
    return execute_query(user_query, params) or []


# ---------------------------------------------------------------------------
# Data fetching — one function per concern.
# ---------------------------------------------------------------------------

def _fetch_stats(is_team: bool, user_id) -> dict:
    rows = _q(_STATS_USER, _STATS_TEAM, is_team, user_id)
    return rows[0] if rows else {}


def _fetch_dow_trend(is_team: bool, user_id) -> dict:
    """Return a {day_name: count} map ordered Mon–Sun."""
    rows = _q(_TREND_USER, _TREND_TEAM, is_team, user_id)
    days = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
    counts = {d: 0 for d in days}
    for row in (rows or []):
        idx = int(row['day_idx'])
        list_idx = (idx - 1) if idx > 0 else 6
        counts[days[list_idx]] = row['count']
    return counts


def _fetch_categories(is_team: bool, user_id) -> dict:
    rows = _q(_CATEGORY_USER, _CATEGORY_TEAM, is_team, user_id)
    raw = rows[0] if rows else {}
    return {k: int(v) for k, v in raw.items()}


def _fetch_trust_trend(is_team: bool, user_id) -> tuple[list, list, list]:
    rows = _q(_TRUST_TREND_USER, _TRUST_TREND_TEAM, is_team, user_id)
    rows = rows or []
    
    # Sort chronological (Ascending) for the graph display
    rows = sorted(rows, key=lambda x: x['date'])
    
    dates, auth, avoid = [], [], []
    for row in rows:
        dates.append(str(row['date']))
        auth.append(float(row['avg_authenticity']) if row['avg_authenticity'] else 0.0)
        avoid.append(float(row['avg_avoidance'])   if row['avg_avoidance']    else 0.0)
    return dates, auth, avoid


def _fetch_excuse_texts(is_team: bool, user_id) -> list[str]:
    rows = _q(_EXCUSE_TEXTS_USER, _EXCUSE_TEXTS_TEAM, is_team, user_id)
    return [row['reason_text'] for row in (rows or []) if row['reason_text']]


def _fetch_delay_records(is_team: bool, user_id) -> list[dict]:
    rows = _q(_DELAY_RECORDS_USER, _DELAY_RECORDS_TEAM, is_team, user_id)
    return [{'authenticity': r['authenticity'], 'submitted_at': r['submitted_at']} for r in (rows or [])]

def _fetch_rationalization_count(is_team: bool, user_id) -> int:
    rows = _q(_RATIONALIZATION_COUNT_USER, _RATIONALIZATION_COUNT_TEAM, is_team, user_id)
    return rows[0]['count'] if rows else 0

def _fetch_precise_risk_history(user_id: int) -> List[Dict[str, Any]]:
    """Fetches exact risk scores and timestamps for kinematics."""
    query = "SELECT risk_score as score, recorded_at as timestamp FROM risk_history WHERE user_id = %s ORDER BY recorded_at DESC LIMIT 15"
    return execute_query(query, (user_id,))


# ---------------------------------------------------------------------------
# Derived metrics
# ---------------------------------------------------------------------------

def _compute_metrics(stats: dict, rationalizations: int) -> dict:
    """Derive delay_rate, avg_risk_val, and wrs from raw stats."""
    from utils.task_formulas import calculate_efficiency_score
    
    total_tasks          = stats.get('total_tasks', 0)
    unique_delayed_tasks = stats.get('unique_delayed_tasks', 0)
    avg_auth             = float(stats.get('avg_auth', 0))
    risk_low             = int(stats.get('risk_low', 0))
    risk_med             = int(stats.get('risk_med', 0))
    risk_high            = int(stats.get('risk_high', 0))

    delay_rate = round((unique_delayed_tasks / total_tasks * 100), 1) if total_tasks > 0 else 0.0
    efficiency = calculate_efficiency_score(total_tasks, rationalizations)

    total_risk_count = risk_low + risk_med + risk_high
    avg_risk_val = (
        ((risk_low * 100) + (risk_med * 50)) / total_risk_count
        if total_risk_count > 0 else 100
    )

    stability_bonus = 10 if delay_rate < 30 else 0
    wrs = round((avg_auth * 0.6) + (avg_risk_val * 0.3) + stability_bonus, 1)

    return {
        'total_tasks':    total_tasks,
        'total_delays':   stats.get('total_delays', 0),
        'avg_auth':       avg_auth,
        'avg_avoid':      float(stats.get('avg_avoid', 0)),
        'risk_low':       risk_low,
        'risk_med':       risk_med,
        'risk_high':      risk_high,
        'delay_rate':     delay_rate,
        'avg_risk_val':   avg_risk_val,
        'wrs':            wrs,
        'efficiency':     efficiency,
    }


# ---------------------------------------------------------------------------
# Lightweight AI Intelligence Functions (Deterministic Heuristics)
# ---------------------------------------------------------------------------

import os

# ...

# Check environment variable for AI enablement
AI_ENABLED = os.getenv("AI_ENABLED", "true").lower() == "true"

def apply_sensitivity(base_score, sensitivity=8.5):
    """
    Apply neural sensitivity multiplier.
    Effective Confidence = Base Confidence * Multiplier
    Sensitivity is passed in to avoid repeated DB hits.
    """
    if sensitivity <= 3:
        multiplier = 0.7  # Lenient
    elif sensitivity <= 6:
        multiplier = 0.9  # Balanced
    elif sensitivity <= 8.5:
        multiplier = 1.0  # Default
    else:
        multiplier = 1.2  # Aggressive

    return min(round(base_score * multiplier, 2), 100)


def _lightweight_similarity_score(texts: list[str], sensitivity: float) -> dict:
    """Detect repeated phrases and calculate a trust penalty."""
    if not texts:
        return {"repeated_keywords": [], "repetition_penalty": 0}
    
    words = []
    for t in texts:
        cleaned = re.findall(r'\b\w+\b', t.lower())
        words.extend(cleaned)

    common = Counter(words)
    # Ignore common stop words implicitly by length and frequency
    repeated_words = [w for w, c in common.items() if c > 2 and len(w) > 4]
    raw_score = min(len(repeated_words) * 5, 25)
    
    # Apply Sensitivity
    repetition_score = apply_sensitivity(raw_score, sensitivity)

    return {
        "repeated_keywords": repeated_words[:5],
        "repetition_penalty": repetition_score
    }

def _detect_behavior_drift(scores: list[float], sensitivity: float) -> dict:
    """Detect if authenticity is suddenly dropping."""
    if len(scores) < 5:
        return {"drift": False, "drop_magnitude": 0}

    recent_avg = sum(scores[-3:]) / 3
    past_avg   = sum(scores[:-3]) / len(scores[:-3])

    if recent_avg < past_avg:
        raw_drop = (past_avg - recent_avg)
        # Apply Sensitivity
        final_drop = apply_sensitivity(raw_drop, sensitivity)
        
        return {
            "drift": final_drop > 15, # Threshold 15
            "drop_magnitude": round(final_drop, 1)
        }
    
    return {"drift": False, "drop_magnitude": 0}

def _calculate_risk_momentum(risk_counts: dict) -> dict:
    """Calculate if risk is escalating."""
    high = risk_counts.get("High", 0)
    med = risk_counts.get("Medium", 0)
    momentum_score = (high * 2) + med

    if momentum_score > 5:
        level = "Escalating"
    elif momentum_score > 2:
        level = "Watch"
    else:
        level = "Stable"

    return {
        "momentum_score": momentum_score,
        "risk_momentum": level
    }

def handle_cold_start(count: int, threshold: int = 5) -> dict:
    """Governance Level D: Maturity Gating."""
    is_cold = count < threshold
    return {
        "is_cold_start": is_cold,
        "sample_size": count,
        "threshold": threshold,
        "status": "Initializing" if is_cold else "Matured"
    }

def _predict_delay_probability(metrics: dict, sensitivity: float) -> dict:
    """Logistic-style formula for future delay probability."""
    delay_rate = metrics.get('delay_rate', 0)
    avg_auth   = metrics.get('avg_auth', 0)
    avg_risk   = metrics.get('avg_risk_val', 100) # High is better here? No, avg_risk_val 100 is low risk

    score = (
        (delay_rate * 0.4) +
        ((100 - avg_auth) * 0.3) +
        ((100 - avg_risk) * 0.3)
    )
    raw_prob = min(max(round(score, 1), 0), 100)
    
    # Apply Sensitivity
    probability = apply_sensitivity(raw_prob, sensitivity)

    return {
        "delay_probability": probability
    }

def _classify_excuse_quality(texts: list[str]) -> dict:
    """Weighted keyword scoring for excuse quality."""
    GENERIC_WORDS = ["issue", "problem", "something", "delay", "urgent", "busy", "personal"]
    SPECIFIC_WORDS = ["invoice", "supplier", "server", "transport", "meeting", "contract", "api", "database"]
    
    generic_count = 0
    total = len(texts)
    
    for text in texts:
        t = text.lower()
        g_hits = sum(1 for w in GENERIC_WORDS if w in t)
        s_hits = sum(1 for w in SPECIFIC_WORDS if w in t)
        if g_hits > s_hits:
            generic_count += 1
            
    ratio = round((generic_count / total * 100), 1) if total > 0 else 0
    
    return {
        "generic_ratio": ratio,
        "quality_label": "High Generic" if ratio > 50 else "Balanced"
    }



# ---------------------------------------------------------------------------
# Advanced Behavioral Intelligence (Phase 1 & 2)
# ---------------------------------------------------------------------------

def _calculate_trust_volatility(scores: list[float]) -> dict:
    """
    Measure variance in authenticity over last N delays.
    High volatility = unstable behavior pattern.
    """
    import statistics
    
    if len(scores) < 3:
        return {"volatility_score": 0, "status": "Stable"}
        
    try:
        stdev = statistics.stdev(scores)
        volatility = round(stdev, 2)
    except Exception:
        volatility = 0

    status = "Stable"
    if volatility > 25:
        status = "Highly Erratic"
    elif volatility > 15:
        status = "Volatile"
    
    return {
        "volatility_score": volatility,
        "status": status
    }

def _analyze_deadline_proximity(dates: list) -> dict:
    """
    Check if delays spike 1-2 days before deadlines, month-end, or Fridays.
    """
    if not dates:
        return {"friday_spike": False, "month_end_spike": False}
        
    friday_count = 0
    month_end_count = 0
    total = len(dates)
    
    for d in dates:
        # d is likely datetime or str, assume datetime handle or conversion
        try:
            if isinstance(d, str):
                dt = datetime.strptime(d, "%Y-%m-%d %H:%M:%S")
            else:
                dt = d
                
            # Friday check (ISO weekday 5)
            if dt.isoweekday() == 5:
                friday_count += 1
                
            # Month end check (day > 25)
            if dt.day > 25:
                month_end_count += 1
        except:
            continue
            
    friday_ratio = (friday_count / total) * 100 if total > 0 else 0
    month_end_ratio = (month_end_count / total) * 100 if total > 0 else 0
    
    return {
        "friday_spike": friday_ratio > 40,
        "month_end_spike": month_end_ratio > 40,
        "friday_ratio": round(friday_ratio, 1)
    }


# ---------------------------------------------------------------------------
# AI enrichment
# ---------------------------------------------------------------------------

def _fetch_delay_records_ex(is_team: bool, user_id) -> list[dict]:
    """
    Fetch delay records tailored for analysis, including authenticity and text.
    Combines logic for time decay and excuse analysis.
    """
    if is_team:
        query = "SELECT score_authenticity AS authenticity, submitted_at, reason_text FROM delays ORDER BY submitted_at DESC LIMIT 30;"
        rows = execute_query(query, ())
    else:
        query = "SELECT score_authenticity AS authenticity, submitted_at, reason_text FROM delays WHERE user_id = %s ORDER BY submitted_at DESC LIMIT 30;"
        rows = execute_query(query, (user_id,))
    rows = rows or []
        
    return [
        {
            'authenticity': r['authenticity'],
            'submitted_at': r['submitted_at'],
            'reason_text': r['reason_text']
        }
        for r in rows
    ]

def _run_ai_analysis(
    is_team: bool,
    user_id,
    metrics: dict,
    trend_auth: list[float],
    sensitivity: float
) -> dict:
    """Run lightweight AI heuristics and traditional models."""
    if not AI_ENABLED:
        return {}
    try:
        from services.ai_insights import generate_ai_insights, generate_executive_summary 
        from services.user_service import compute_behavioral_state
        
        # Phase 3: Computation Throttling
        processor = BackgroundProcessor.get_instance()
        high_load = processor.get_queue_size() > 1
        
        # Optimization: Single query for both time-decay and NLP analysis
        combined_records = _fetch_delay_records_ex(is_team, user_id)
        
        if high_load:
            logger.info(f"High load detected (Q={processor.get_queue_size()}). Throttling analytics for user {user_id}")
            # Ensure return matches _empty_ai_schema/analytics expected structure
            return {
                "ai": {
                    "behavioral_intelligence_score": 0,
                    "confidence": {"score": 50, "label": "Throttled"},
                    "trust_volatility": {"volatility_score": 0, "status": "Throttled"},
                    "cognitive_patterns": {"hedging_score": 0, "status": "Throttled"},
                    "explainability": {"auth_component": 0, "risk_component": 0, "delay_penalty": 0}
                },
                "v1_intelligence": {
                    "integrity_index": {"score": 50, "status": "Throttled"},
                    "rolling_avg_risk": 50,
                    "kinematics": {"risk_velocity": 0, "risk_acceleration": 0}
                },
                "delay_probability": 0,
                "throttled": True
            }
        
        # Extract what we need
        delay_records = combined_records # passed to time decay
        excuse_texts = [r['reason_text'] for r in combined_records if r['reason_text']]
        # Limit to 20 for NLP as per original spec if needed, or keep 30
        excuse_texts = excuse_texts[:20]

        from services.nlp_service import (
            analyze_hedging_and_defensiveness, 
            calculate_over_explanation_score, 
            check_consistency_variance,
            analyze_excuse_sentiment,
            cluster_excuse_patterns
        )
        from services.intelligence_engine import (
            calculate_rolling_risk,
            calculate_kinematics,
            calculate_integrity_index
        )

        # 1. Implementation of the 5 Light AI Improvements
        similarity_ai = _lightweight_similarity_score(excuse_texts, sensitivity)
        drift_ai      = _detect_behavior_drift(trend_auth, sensitivity)
        
        # New Phase 1 & 2 Metrics
        volatility_ai = _calculate_trust_volatility(trend_auth)
        
        # Extract dates for proximity check
        delay_dates = [r['submitted_at'] for r in combined_records if r.get('submitted_at')]
        proximity_ai = _analyze_deadline_proximity(delay_dates)
        
        # Advanced NLP on the standard excuse texts
        # We aggregate specific metrics across the recent batch
        hedging_scores = []
        over_explain_scores = []
        consistency_scores = []
        
        # Clustering (Phase 2)
        clustering_ai = cluster_excuse_patterns(excuse_texts)
        
        # Optimization: Process only top 5 recent excuses for deeper NLP
        # Analyzing 20 items with multiple NLP calls per item is too heavy for Free Tier CPU.
        sample_texts = excuse_texts[:5] 
        
        for i, text in enumerate(sample_texts):
            # Hedging
            h = analyze_hedging_and_defensiveness(text)
            hedging_scores.append(h['score'])
            
            # Over-Explanation (needs subjectivity)
            sent = analyze_excuse_sentiment(text)
            oe = calculate_over_explanation_score(text, sent['subjectivity'])
            over_explain_scores.append(oe['score'])
            
            # Consistency (compare current vs rest of history)
            # past_texts excludes current one
            past_texts = sample_texts[i+1:] + sample_texts[:i] 
            c = check_consistency_variance(text, past_texts)
            consistency_scores.append(c['score'])

        avg_hedging = round(sum(hedging_scores)/len(hedging_scores)) if hedging_scores else 0
        avg_over_explain = round(sum(over_explain_scores)/len(over_explain_scores)) if over_explain_scores else 0
        avg_consistency = round(sum(consistency_scores)/len(consistency_scores)) if consistency_scores else 100

        # Tier 3: Manipulation & Integrity
        import json
        manip_flags_all = []
        entropies = []
        for r in combined_records:
            analysis = r.get('ai_analysis_json')
            if isinstance(analysis, str):
                try: analysis = json.loads(analysis)
                except: analysis = {}
            if not analysis: continue
            
            if 'manipulation_flags' in analysis:
                manip_flags_all.extend(analysis['manipulation_flags'])
            if 'entropy' in analysis:
                entropies.append(analysis['entropy'])
        
        avg_entropy = round(sum(entropies)/len(entropies), 2) if entropies else 0
        manip_count = len(manip_flags_all)

        # ... (rest of legacy calculations) ...
        
        risk_dist = {
            "Low": metrics.get('risk_low', 0),
            "Medium": metrics.get('risk_med', 0),
            "High": metrics.get('risk_high', 0)
        }
        from services.user_service import get_user_momentum
        momentum_tier2 = get_user_momentum(user_id) if not is_team else {}
        
        momentum_ai    = _calculate_risk_momentum(risk_dist)
        prediction_ai  = _predict_delay_probability(metrics, sensitivity)
        quality_ai     = _classify_excuse_quality(excuse_texts)
        
        # Tier 5: Cognitive Signals
        b_state_ai = compute_behavioral_state(user_id) if not is_team else {"state": "N/A"}
        team_resilience = get_team_resilience_index()
        
        # --- NEW v1.1 ELITE INTELLIGENCE INTEGRATION ---
        task_counts = metrics.get('total_delays', 0)
        cold_start = handle_cold_start(task_counts)
        
        # Calculate Rolling Risk & Kinematics (Time-Normalized)
        precise_history = _fetch_precise_risk_history(user_id)
        kinematics = calculate_kinematics(precise_history)
        
        # Calculate Integrity Index
        entropy_val = quality_ai.get('generic_ratio', 50) # Use generic ratio as proxy for entropy
        volatility_val = volatility_ai.get('volatility_score', 0)
        manip_risk = manip_count * 10
        integrity = calculate_integrity_index({
            'manip_risk': manip_risk,
            'volatility': volatility_val,
            'entropy':    entropy_val,
        })
        
        # --- RECOMMENDATION ENGINE (Logic-First) ---
        recommendations = []
        if metrics.get('delay_rate', 0) > 30:
            recommendations.append("Suggest earlier progress updates (Pre-Deadline Checkpoint).")
        if avg_hedging > 60:
            recommendations.append("Suggest clearer accountability phrasing (Outcome-Based Focus).")
        if volatility_val > 20:
            recommendations.append("Suggest workload review / Complexity Throttling.")
        if integrity['status'] == "High Risk":
            recommendations.append("Initiate Manual Audit / Institutional Review.")
            
        # 2. Breakdown calculation for Explainable AI
        auth_component   = round(metrics.get('avg_auth', 0) * 0.4, 1)
        risk_component   = round(metrics.get('avg_risk_val', 100) * 0.3, 1)
        delay_penalty    = round(metrics.get('delay_rate', 0) * 0.2, 1)
        risk_momentum    = momentum_ai['risk_momentum']
        momentum_penalty = 10 if risk_momentum == "Escalating" else 0
        
        # New penalties
        hedging_penalty = 10 if avg_hedging > 50 else 0
        volatility_penalty = 15 if volatility_ai['status'] == "Highly Erratic" else 0
        integrity_penalty = min(25, manip_count * 8) # Cap at 25

        behavioral_intel = max(
            0,
            round(auth_component + risk_component - delay_penalty - momentum_penalty - hedging_penalty - volatility_penalty - integrity_penalty, 1)
        )

        ai_payload = {
            'behavioral_intelligence_score': behavioral_intel,
            'risk_momentum':                 risk_momentum,
            'integrity_ai': {
                'avg_entropy': avg_entropy,
                'manipulation_count': manip_count,
                'flags': list(set(manip_flags_all)),
                'status': 'Compromised' if manip_count > 2 else ('Warning' if manip_count > 0 else 'Nominal')
            },
            'delay_probability':             prediction_ai['delay_probability'],
            'behavior_drift':                drift_ai['drift'],
            'drift_magnitude':               drift_ai['drop_magnitude'],
            'excuse_quality':                quality_ai['quality_label'],
            
            # Tier 5 Cognitive Signals
            'behavioral_state': b_state_ai,
            'team_resilience': team_resilience,

            # Advanced Behavioral Metrics
            'trust_volatility': volatility_ai,
            'deadline_proximity': proximity_ai,
            'cognitive_patterns': {
                'hedging_score': avg_hedging,
                'over_explanation_score': avg_over_explain,
                'consistency_score': avg_consistency,
                'clustering_data': clustering_ai
            },
            
            'explainability': {
                'auth_component':   auth_component,
                'risk_component':   risk_component,
                'delay_penalty':    delay_penalty,
                'momentum_penalty': momentum_penalty,
                'hedging_penalty':  hedging_penalty,
                'volatility_penalty': volatility_penalty,
                'final_score':      behavioral_intel
            },

            # v1.0 Intelligence Layer
            'v1_intelligence': {
                'integrity_index': integrity,
                'kinematics': kinematics,
                'cold_start': cold_start,
                'recommendations': recommendations,
                'rolling_avg_risk': calculate_rolling_risk(metrics.get('avg_auth', 0), behavioral_intel)
            },

            # ---- AI Confidence Calculation ----
            'confidence': (lambda: {
                'score': (score := max(0, min(100, 
                    min(metrics.get('total_delays', 0) * 5, 40) + 
                    (20 if metrics.get('delay_rate', 0) < 30 else 10) - 
                    (10 if drift_ai['drift'] else 0) - 
                    (10 if drift_ai['drop_magnitude'] > 30 else 0)
                ))),
                'label': "High" if score >= 75 else "Moderate" if score >= 40 else "Low",
                'data_points': metrics.get('total_delays', 0),
                'stability_factor': (20 if metrics.get('delay_rate', 0) < 30 else 10)
            })(),

            # Internal/Legacy data if needed for graphs
            'excuse_ai':     similarity_ai,
            'drift_ai':      drift_ai,
            'momentum_ai':   momentum_ai,
            'momentum_signals': momentum_tier2 if not is_team else {},
            'prediction_ai': prediction_ai,
            'quality_ai':    quality_ai,
            'time_decay_ai': calculate_time_decay_score(delay_records) if delay_records else {"score": 0},
            
            # Metadata for Governance Audit
            'metadata': {
                'model_version': MODEL_VERSION,
                'weight_schema_version': WEIGHT_SCHEMA_VERSION,
                'decay_lambda': DECAY_LAMBDA,
                'normalization_version': NORMALIZATION_VERSION
            }
        }
        
        # Integrate Insights & Summary
        role_for_ai = "admin" if is_team else "employee" # Fallback if specific role not passed deep
        ai_payload['ai_insights'] = generate_ai_insights(metrics, ai_payload, role=role_for_ai)
        ai_payload['executive_summary'] = generate_executive_summary(role_for_ai, metrics, ai_payload)
        
        return ai_payload
    except Exception as e:
        logger.error("AI analysis failed: %s", e)
        return {}


# ---------------------------------------------------------------------------
# Graph builders — presentation config isolated from data logic.
# ---------------------------------------------------------------------------

_TRANSPARENT  = "rgba(0,0,0,0)"
_FONT_GLASS    = {"color": "#e2e8f0", "family": "Inter, sans-serif"}
_GRID_COLOR    = "rgba(255,255,255,0.05)"
_BASE_LAYOUT  = {
    "paper_bgcolor": _TRANSPARENT, 
    "plot_bgcolor": _TRANSPARENT, 
    "font": _FONT_GLASS,
    "margin": {"t": 40, "b": 40, "l": 40, "r": 40},
    "xaxis": {"gridcolor": _GRID_COLOR, "zerolinecolor": _GRID_COLOR},
    "yaxis": {"gridcolor": _GRID_COLOR, "zerolinecolor": _GRID_COLOR}
}


def _gauge(value: float, title: str, bar_color: str, steps: list) -> dict:
    return {
        "data": [{
            "type": "indicator", "mode": "gauge+number", "value": value,
            "title": {"text": title},
            "gauge": {"axis": {"range": [0, 100]}, "bar": {"color": bar_color}, "steps": steps},
        }],
        "layout": _BASE_LAYOUT,
    }


def _build_graphs(metrics: dict, dow_counts: dict, categories: dict,
                  trend_dates: list, trend_auth: list, trend_avoid: list, ai_data: dict) -> dict:
    rl, rm, rh = metrics['risk_low'], metrics['risk_med'], metrics['risk_high']
    days = list(dow_counts.keys())

    return {
        "status_pie": {
            "data": [{"labels": ["Low", "Medium", "High"], "values": [rl, rm, rh], "type": "pie",
                      "hole": 0.4, "marker": {"colors": ["#10b981", "#f59e0b", "#ef4444"]}}],
            "layout": {**_BASE_LAYOUT, "title": "Risk Level Distribution"},
        },
        "gauge_auth": _gauge(
            round(metrics['avg_auth'], 1), "Avg Authenticity", "#10b981",
            [{"range": [0,  40], "color": "rgba(239,68,68,0.2)"},
             {"range": [40, 70], "color": "rgba(245,158,11,0.2)"},
             {"range": [70,100], "color": "rgba(16,185,129,0.2)"}],
        ),
        "gauge_avoidance": _gauge(
            round(metrics['avg_avoid'], 1), "Avg Avoidance", "#ef4444",
            [{"range": [0,  20], "color": "rgba(16,185,129,0.2)"},
             {"range": [20, 50], "color": "rgba(245,158,11,0.2)"},
             {"range": [50,100], "color": "rgba(239,68,68,0.2)"}],
        ),
        "gauge_wrs": _gauge(
            metrics['wrs'], "Reliability Index", "#6366f1",
            [{"range": [0,  50], "color": "rgba(239,68,68,0.15)"},
             {"range": [50, 80], "color": "rgba(245,158,11,0.15)"},
             {"range": [80,100], "color": "rgba(99,102,241,0.15)"}],
        ),
        "gauge_probability": _gauge(
            ai_data.get('prediction_ai', {}).get('delay_probability', 0), "Delay Probability", "#a855f7",
            [{"range": [0,  30], "color": "rgba(16,185,129,0.15)"},
             {"range": [30, 60], "color": "rgba(245,158,11,0.15)"},
             {"range": [60,100], "color": "rgba(168,85,247,0.15)"}],
        ),
        "gauge_confidence": _gauge(
            ai_data.get('confidence', {}).get('score', 0), "AI Confidence", "#3b82f6",
            [{"range": [0,  40], "color": "rgba(239,68,68,0.2)"},
             {"range": [40, 75], "color": "rgba(245,158,11,0.2)"},
             {"range": [75,100], "color": "rgba(59,130,246,0.2)"}],
        ),
        "line_chart": {
            "data": [{"x": days, "y": list(dow_counts.values()), "type": "scatter",
                      "mode": "lines+markers", "line": {"color": "#10b981", "width": 4, "shape": "spline"},
                      "marker": {"size": 10, "color": "#34d399"}}],
            "layout": {**_BASE_LAYOUT, "title": "Strategic Trend (Day of Week)",
                       "xaxis": {"title": "Day"}, "yaxis": {"title": "Delay Volume"}},
        },
        "trend_over_time": {
            "data": [
                {"x": trend_dates, "y": trend_auth, "type": "scatter", "mode": "lines+markers",
                 "name": "Authenticity", "line": {"color": "#10b981", "width": 3, "shape": "spline"}, "marker": {"size": 8}},
                {"x": trend_dates, "y": trend_avoid, "type": "scatter", "mode": "lines+markers",
                 "name": "Avoidance",  "line": {"color": "#ef4444", "width": 3, "shape": "spline"}, "marker": {"size": 8}},
            ],
            "layout": {**_BASE_LAYOUT, "title": "Score Trends Over Time",
                       "xaxis": {"title": "Date"}, "yaxis": {"title": "Score"},
                       "showlegend": True, "legend": {"orientation": "h", "x": 0, "y": 1.15}},
        },
        "categories": {
            "data": [{"x": list(categories.keys()), "y": list(categories.values()),
                      "type": "bar", "marker": {"color": "#6366f1", "line": {"width": 1, "color": "#818cf8"}}}],
            "layout": {**_BASE_LAYOUT, "title": "Top Delay Reasons"},
        },
    }

# ---------------------------------------------------------------------------
# Global Benchmarking (Population Context)
# ---------------------------------------------------------------------------

_GLOBAL_BENCHMARK_CACHE = {"data": None, "expires": 0}
_BENCHMARK_TTL = 300 # 5 minutes

def get_population_benchmarks() -> dict:
    """
    Computes population-wide behavioral distributions.
    Governance Level D: Comparative Social Context.
    """
    global _GLOBAL_BENCHMARK_CACHE
    now = time.time()
    
    if _GLOBAL_BENCHMARK_CACHE["data"] and now < _GLOBAL_BENCHMARK_CACHE["expires"]:
        return _GLOBAL_BENCHMARK_CACHE["data"]

    try:
        from database.connection import get_db_cursor
        with get_db_cursor() as cur:
            # Aggregate from user_analytics_summary for efficiency
            cur.execute("""
                SELECT 
                    AVG(avg_authenticity) as mean_auth,
                    STDDEV(avg_authenticity) as std_auth,
                    AVG(avg_avoidance) as mean_avoid,
                    STDDEV(avg_avoidance) as std_avoid,
                    COUNT(*) as population_size
                FROM user_analytics_summary
                WHERE delay_count_total > 2
            """)
            row = cur.fetchone()
            
            benchmarks = {
                "auth": {"mean": float(row['mean_auth'] or 0), "std": float(row['std_auth'] or 15)},
                "risk": {"mean": float(row['mean_avoid'] or 0), "std": float(row['std_avoid'] or 15)},
                "population_size": int(row['population_size'] or 0),
                "timestamp": datetime.now().isoformat()
            }
            
            _GLOBAL_BENCHMARK_CACHE = {"data": benchmarks, "expires": now + _BENCHMARK_TTL}
            return benchmarks
    except Exception as e:
        logger.error("Failed to compute population benchmarks: %s", e)
        return {"auth": {"mean": 50, "std": 15}, "risk": {"mean": 50, "std": 15}, "population_size": 0}

def calculate_user_peer_relativity(user_id: int, current_risk: float) -> dict:
    """
    Calculates a user's Z-score and percentile ranking relative to the workforce.
    """
    benchmarks = get_population_benchmarks()
    pop_risk = benchmarks["risk"]
    
    # Z-Score Calculation: (x - mu) / sigma
    mu = pop_risk["mean"]
    sigma = pop_risk["std"] if pop_risk["std"] > 0 else 1.0
    
    z_score = (current_risk - mu) / sigma
    
    # Percentile approximation (Normal Distribution)
    percentile = 0.5 * (1 + math.erf(z_score / math.sqrt(2)))
    
    return {
        "z_score": round(z_score, 2),
        "percentile": round(percentile * 100, 1),
        "population_mean": round(mu, 2),
        "deviation_type": "above_average" if z_score > 0.5 else ("below_average" if z_score < -0.5 else "nominal")
    }

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_task_intelligence(task_id: int) -> dict:
    """
    Fetch comprehensive behavioral intelligence for a specific task.
    Priority: 1. Snapshot from DB, 2. Dynamic Recalculation (Fallback).
    """
    try:
        from repository.delays_repo import get_delays_by_task
        from repository.tasks_repo import get_task_by_id
        from services.intelligence_engine import TaskIntelligenceEngine
        import json
        
        task = get_task_by_id(task_id)
        if not task: return {}
            
        delays = get_delays_by_task(task_id)
        if not delays:
            return {
                "intelligence_available": False,
                "neural_console": {
                    "task_risk": {"score": 0, "label": "STABLE"},
                    "stability": {"score": 100, "label": "STABLE"},
                    "integrity": {"score": 100, "label": "SECURE"}
                },
                "features": {},
                "flags": [],
                "snapshots_active": False,
                "engine_version": "N/A",
                "recommendations": [],
                "kinematics": {},
                "user_rolling_avg": 0,
                "peer_comparison": {
                    "percentile": 0,
                    "z_score": 0.0,
                    "population_mean": 0,
                    "deviation_type": "nominal"
                }
            }
            
        # 1. Load Snapshot if available (Governance Level C)
        latest_delay = delays[0]
        snapshot = {}
        ai_raw = latest_delay.get('ai_analysis_json')
        
        if ai_raw:
            try:
                if isinstance(ai_raw, str): snapshot = json.loads(ai_raw)
                else: snapshot = ai_raw
            except: pass

        # 2. Extract Data from Snapshot or Fallback to Engine
        if snapshot and 'feature_vector' in snapshot:
            features = snapshot['feature_vector']
            task_score = snapshot['risk_score']
            flags = snapshot['flags']
            engine_v = snapshot.get('engine_version', '1.0')
        else:
            # Fallback to dynamic engine (ensures backward compatibility for legacy delays)
            engine = TaskIntelligenceEngine(task.get('user_id'))
            text = latest_delay.get('reason_text', '')
            delay_days = latest_delay.get('delay_duration', 0)
            pressure = 50 # Fallback pressure
            
            features = engine.extract_features(text, delay_days, pressure, delays)
            task_score = engine.compute_task_risk()
            flags = engine.trigger_flags()
            engine_v = "1.1 (Fallback)"

        # 3. User Level Context (Evolution & Kinematics)
        user_id = task.get('user_id')
        user_ai = get_ai_intelligence(user_id, 'manager') or {}
        
        # Safe extraction from normalized schema
        ai_root = user_ai.get('ai', {}) or {}
        v1 = user_ai.get('v1_intelligence', {}) or {}
        
        # 4. Neural Console Data
        neural_console = {
            "task_risk": {
                "score": task_score,
                "label": "CRITICAL" if task_score > 75 else ("HIGH" if task_score > 50 else "STABLE")
            },
            "stability": {
                "score": 100 - ai_root.get('trust_volatility', {}).get('volatility_score', 0),
                "label": ai_root.get('trust_volatility', {}).get('volatility_label', 'STABLE')
            },
            "integrity": {
                "score": v1.get('integrity_index', {}).get('score', 85),
                "label": v1.get('integrity_index', {}).get('status', 'SECURE')
            }
        }
        
        # 5. Peer Comparison (Level D)
        peer_relativity = calculate_user_peer_relativity(user_id, task_score)
        
        return {
            "intelligence_available": True,
            "neural_console": neural_console,
            "features": features,
            "flags": flags,
            "snapshots_active": 'feature_vector' in snapshot,
            "engine_version": engine_v,
            "recommendations": v1.get('recommendations', []),
            "kinematics": v1.get('kinematics', {}),
            "user_rolling_avg": v1.get('rolling_avg_risk', 0),
            "peer_comparison": peer_relativity
        }
        
    except Exception as e:
        logger.error("get_task_intelligence error: %s", e, exc_info=True)
        return {"intelligence_available": False, "error": str(e)}

def _fetch_neural_sensitivity() -> float:
    """Fetch neural sensitivity configuration once."""
    try:
        res = execute_query("SELECT neural_sensitivity FROM system_config WHERE id=1", fetch=True)
        return float(res[0]['neural_sensitivity']) if res else 8.5
    except Exception:
        return 8.5

def get_overview_data(user_id, role: str) -> dict:
    """
    Fetch lightweight overview stats (gauges, risk distribution).
    No graphs, no heavy AI.
    """
    if not user_id:
        return _empty_ai_schema()
    
    cache_key = f"overview_{user_id}_{role}"
    cached = _get_cached(cache_key)
    if cached: 
        # Ensure wrs_score is present in cached data if it was missing
        if 'wrs_score' not in cached:
            cached['wrs_score'] = cached.get('wrs', 0)
        return cached.copy()
        
    is_team = role in ('admin', 'manager')
    stats = _fetch_stats(is_team, user_id)
    # rationalizations = _fetch_rationalization_count(is_team, user_id)
    rationalizations = int(stats.get('risk_high', 0))
    metrics = _compute_metrics(stats, rationalizations)

    result = {
        "avg_auth_score": round(metrics['avg_auth'], 1),
        "avg_avoidance_score": round(metrics['avg_avoid'], 1),
        "wrs_score": metrics['wrs'],
        "wrs": metrics['wrs'], # Redundant but safe
        "delay_rate": metrics['delay_rate'],
        "risk_distribution": {
            "Low": metrics['risk_low'],
            "Medium": metrics['risk_med'],
            "High": metrics['risk_high'],
        },
        "efficiency": metrics['efficiency'],
        "categories": _fetch_categories(is_team, user_id),
        # Basic gauge needs
        "risk_low": metrics['risk_low'],
        "risk_med": metrics['risk_med'],
        "risk_high": metrics['risk_high'],
        "total_delays": metrics['total_delays'],
    }
    
    _set_cached(cache_key, result)
    return result


def trigger_async_refill(user_id, role):
    """Enqueues a background task to refresh the AI Intelligence Cache."""
    processor = BackgroundProcessor.get_instance()
    if processor.get_queue_size() > 5:
        logger.warning(f"Background queue under pressure ({processor.get_queue_size()}), skipping refill for user {user_id}")
        return
    processor.submit_task(_force_get_ai_intelligence, user_id, role)

def _force_get_ai_intelligence(user_id, role):
    """
    Inner worker that forces a full re-run of AI intelligence and updates the DB cache.
    Runs in a background thread, so it pushes a Flask app context explicitly to
    ensure flask.g and DB connection pooling work correctly outside a request context.
    """
    if not user_id:
        return _empty_ai_schema()

    # Push app context for background thread safety (flask.g, DB pool, etc.)
    try:
        from flask import current_app
        ctx = current_app._get_current_object().app_context()
        ctx.push()
    except RuntimeError:
        # No app available (e.g., unit test env) — try to proceed anyway
        ctx = None
        logger.warning("_force_get_ai_intelligence: no Flask app context available, proceeding without push.")

    try:
        is_team = role in ('admin', 'manager')
        sensitivity = _fetch_neural_sensitivity()
        stats = _fetch_stats(is_team, user_id)
        rationalizations = int(stats.get('risk_high', 0))
        metrics = _compute_metrics(stats, rationalizations)
        trend_dates, t_auth, t_avoid = _fetch_trust_trend(is_team, user_id)
        ai_results = _run_ai_analysis(is_team, user_id, metrics, t_auth, sensitivity)

        if AI_ENABLED and ai_results:
            from services.ai_insights import generate_ai_insights
            from services.ai_service import generate_executive_dashboard_summary

            analytics_summary = {
                "risk_distribution": {"Low": metrics['risk_low'], "Medium": metrics['risk_med'], "High": metrics['risk_high']},
                "avg_auth_score": metrics['avg_auth'],
                "avg_avoidance_score": metrics['avg_avoid'],
                "delay_rate": metrics['delay_rate'],
            }
            ai_insights = generate_ai_insights(analytics_summary, ai_results)

            v1 = ai_results.get('v1_intelligence', {})
            analytic_state = {
                "role": role,
                "tri_score": stats.get('tri_score', 100),
                "hedging_score": round(ai_results.get('cognitive_patterns', {}).get('hedging_score', 0) / 100.0, 2),
                "trust_volatility": round(ai_results.get('trust_volatility', {}).get('volatility_score', 0) / 100.0, 2),
                "predictive_delay_probability": round(ai_results.get('delay_probability', 0) / 100.0, 2),
                "integrity_index": round(v1.get('integrity_index', {}).get('score', 0) / 100.0, 2),
                "executive_state": "behavioral_instability_detected" if v1.get('rolling_avg_risk', 0) > 60 else "stable",
                "confidence_level": round(ai_results.get('confidence', {}).get('score', 0) / 100.0, 2)
            }
            exec_data = generate_executive_dashboard_summary(analytic_state)
            ai_results['structured_executive_summary'] = exec_data

            team_resilience = get_team_resilience_index()
            result_to_cache = _merge_with_schema({
                "ai": _filter_ai_data_by_role(ai_results, role),
                "ai_insights": ai_insights,
                "executive_summary": exec_data.get('summary', ''),
                "wrs_score": metrics['wrs'],
                "team_resilience": team_resilience,
                "cached_at": datetime.now().isoformat()
            })


            execute_query("DELETE FROM ai_snapshots WHERE user_id = %s AND role = %s", (user_id, role), fetch=False)
            execute_query(
                "INSERT INTO ai_snapshots (user_id, role, summary_json) VALUES (%s, %s, %s)",
                (user_id, role, json.dumps(result_to_cache)),
                fetch=False
            )
            logger.info(f"Background AI refill complete for user {user_id} (role={role}).")
            return result_to_cache
    except Exception as e:
        logger.error(f"Background AI refill failed for user {user_id}: {e}", exc_info=True)
        return _empty_ai_schema()
    finally:
        if ctx:
            ctx.pop()
def get_ai_intelligence(user_id, role: str) -> dict:
    """
    Fetch AI analysis with Stale-While-Revalidate logic.
    Returns cached data instantly, triggers background refresh if stale or missing.
    """
    if not user_id:
        return _empty_ai_schema()

    # --- Elite Level D+: Stale-While-Revalidate ---
    try:
        cache_query = """
            SELECT summary_json, created_at FROM ai_snapshots 
            WHERE user_id = %s AND role = %s
            ORDER BY created_at DESC LIMIT 1
        """
        cached = execute_query(cache_query, (user_id, role), fetch=True)
        
        if cached:
            full_data = cached[0]['summary_json']
            created_at = cached[0]['created_at']
            
            # TZ-Aware comparison fixing the "naive vs aware" TypeError risk
            now = datetime.now(timezone.utc)
            if created_at.tzinfo is None:
                created_at = created_at.replace(tzinfo=timezone.utc)
            
            age_seconds = (now - created_at).total_seconds()
            
            # If fresh (< 5 mins), return instantly
            if age_seconds < 300:
                return _merge_with_schema(full_data)
            
            # If stale (5-30 mins), return stale AND trigger background refill
            if age_seconds < 1800:
                logger.info(f"Serving STALE AI Intelligence for user {user_id}. Triggering refill.")
                trigger_async_refill(user_id, role)
                return _merge_with_schema(full_data)
    except Exception as e:
        logger.warning(f"Cache lookup failed: {e}")

    # If missing or very old, return processing state and trigger refill
    logger.info(f"AI Cache MISS/EXPIRED for user {user_id}. Enqueueing job.")
    trigger_async_refill(user_id, role)
    
    # Return placeholder normalized by schema
    base = {
        "wrs_score": 0,
        "peer_comparison": {
            "percentile": 0,
            "z_score": 0.0,
            "label": "CALIBRATING",
            "population_mean": 0
        },
        "ai": {
            "behavioral_profile": "NEURAL_COLD_START",
            "risk_flags": [],
            "cognitive_load": "MINIMAL"
        },
        "ai_insights": [],
        "executive_summary": "Neural engine is initializing. Submit your first delay to activate cognitive analysis.",
        "v1_intelligence": {},
        "team_resilience": {"score": 100, "label": "CALIBRATING"},
        "behavioral_state": {"state": "INITIALIZING"},
        "processing": True
    }
    return _merge_with_schema(base)



def _filter_ai_data_by_role(ai_data: dict, role: str) -> dict:
    """
    Sanitizes AI data based on user role with Anti-Gaming protection.
    
    Employee: 
      - Sees "Encouragement" stats (Reliability, Stability). 
      - Hides Deception scores.
      - Converts cognitive scores to vague labels (Low/Medium/High).
    
    Manager: 
      - Sees "Risk Oversight" stats (Drift, Trend, Recycled Excuses).
      - Hides internal formulas/weights.
      - Sees qualitative flags instead of raw detection numbers.
      
    Admin: 
      - Sees "Forensic" stats (Cross-User Similarity, Global Volatility).
    """
    if not ai_data:
        return {}
    
    def _score_to_label(score, buffer=0):
        """Map numeric score to vague label."""
        if score is None: return "Unknown"
        # Add slight random buffer in real implementation to prevent edge-probing
        val = float(score) + buffer
        if val < 20: return "Low"
        if val < 40: return "Moderate"
        if val < 70: return "Elevated"
        return "High"

    # Common safe metrics for everyone
    filtered = {
        'behavioral_intelligence_score': ai_data.get('behavioral_intelligence_score'),
        'delay_probability': ai_data.get('delay_probability'),
        'risk_momentum': ai_data.get('risk_momentum'), 
        'confidence': ai_data.get('confidence'),
        'explainability': {
            'final_score': ai_data.get('explainability', {}).get('final_score')
        }
    }
    
    # Employee View (Constructive & Anti-Gaming)
    if role == 'employee':
        # Show specific components relative to improvement
        filtered['explainability']['auth_component'] = ai_data.get('explainability', {}).get('auth_component')
        filtered['explainability']['delay_penalty'] = ai_data.get('explainability', {}).get('delay_penalty')
        
        # Soften cognitive patterns to labels
        if 'cognitive_patterns' in ai_data:
            cp = ai_data['cognitive_patterns']
            filtered['cognitive_patterns'] = {
                'hedging_risk': _score_to_label(cp.get('hedging_score')),
                'consistency_check': "Pass" if cp.get('consistency_score') > 70 else "Review Needed",
                'clarity_level': "Concise" if cp.get('over_explanation_score') < 40 else "Verbose"
            }
        return filtered

    # Manager View (Risk Oversight)
    if role == 'manager':
        # Add Drift, Volatility, and quality labels
        filtered['behavior_drift'] = ai_data.get('behavior_drift')
        filtered['drift_magnitude'] = ai_data.get('drift_magnitude')
        filtered['excuse_quality'] = ai_data.get('excuse_quality')
        filtered['trust_volatility'] = ai_data.get('trust_volatility')
        
        # Add expanded explainability
        filtered['explainability'] = ai_data.get('explainability') 
        
        # Cognitive patterns (Manager sees high-level patterns with labels)
        if 'cognitive_patterns' in ai_data:
            cp = ai_data['cognitive_patterns']
            filtered['cognitive_patterns'] = {
                'hedging_score': _score_to_label(cp.get('hedging_score')), # Still labeled to avoid weight guessing
                'consistency_score': cp.get('consistency_score'), # Managers might need raw score for coaching
                'consistency_label': _score_to_label(100 - cp.get('consistency_score', 100)),
                'clustering_data': cp.get('clustering_data') # Managers can see themes
            }
            
        return filtered

    # Admin View (System Intelligence)
    if role == 'admin':
        # Returns everything, including raw debug data
        return ai_data
        
    return filtered


def get_trend_data(user_id, role: str) -> dict:
    """
    Fetch historical trends and categories.
    """
    if not user_id:
        return {
            "dow_counts": {},
            "categories": {},
            "trend_dates": [],
            "trend_auth": [],
            "trend_avoid": []
        }

    cache_key = f"trends_{user_id}_{role}"
    cached = _get_cached(cache_key)
    if cached: return cached.copy()

    is_team = role in ('admin', 'manager')

    dow_counts = _fetch_dow_trend(is_team, user_id)
    categories = _fetch_categories(is_team, user_id)
    trend_dates, t_auth, t_avoid = _fetch_trust_trend(is_team, user_id)

    total_cat_count = sum(categories.values()) if isinstance(categories, dict) else 0
    has_data = bool(trend_dates) and (total_cat_count > 0 or bool(dow_counts))

    # We return raw data to let frontend build charts or use simple server-side construction
    # Ideally frontend builds charts from JSON to save bandwidth.
    # Sanitize dates for JSON serialization (prevents 500 in templates)
    # If no data, provide a baseline trend for UI stability
    if not trend_dates:
        # Generate last 7 days as placeholder dates
        from datetime import timedelta
        end = datetime.now()
        trend_dates = [(end - timedelta(days=i)) for i in range(6, -1, -1)]
        t_auth = [75.0] * 7
        t_avoid = [25.0] * 7

    safe_dates = [d.strftime("%Y-%m-%d") if isinstance(d, datetime) else str(d) for d in trend_dates]

    result = {
        "dow_counts": dow_counts,
        "categories": categories,
        "trend_dates": safe_dates,
        "trend_auth": t_auth,
        "trend_avoid": t_avoid,
        "has_data": has_data,
        "total_cat_count": total_cat_count,
        "calibrating": not has_data
    }
    _set_cached(cache_key, result)
    return result


def get_analytics_data(user_id, role: str) -> dict:
    """
    Legacy wrapper for backward compatibility with dashboard_routes.py.
    Fetches full data including AI insights to populate the dashboard sidebar.
    """
    # 1. Get base overview data (stats, gauges)
    data = get_overview_data(user_id, role)
    
    # 2. Enriched with AI data (if available) for the sidebar insights
    try:
        ai_data = get_ai_intelligence(user_id, role)
        data['ai_insights'] = ai_data.get('ai_insights', [])
        data['efficiency'] = ai_data.get('efficiency', data.get('efficiency', 0))
        
        # Tier 5 Cognitive Signals
        data['team_resilience'] = ai_data.get('team_resilience', {'score': 100, 'label': 'NOMINAL'})
        data['behavioral_state'] = ai_data.get('behavioral_state', {'state': 'STABLE'})
        
    except Exception as e:
        logger.error(f"Legacy get_analytics_data AI fetch failed: {e}")
        data['ai_insights'] = []
        
    return data


import threading

# Thread-safe cache for systemic metrics (Tier 5)
_systemic_cache = {
    'tri': {'data': None, 'expires': 0},
    'contagion': {'data': None, 'expires': 0}
}
_cache_lock = threading.Lock()
CACHE_TTL = 300  # 5 minutes

def get_team_resilience_index() -> dict:
    """
    Tier 5: Collective Resilience.
    Aggregates individual Hidden Markov States into a weighted systemic health score.
    Includes 5-minute caching to prevent redundant batch processing.
    """
    global _systemic_cache
    now = time.time()
    
    with _cache_lock:
        if _systemic_cache['tri']['data'] and now < _systemic_cache['tri']['expires']:
            return _systemic_cache['tri']['data']
            
    from repository.users_repo import get_all_users
    from services.user_service import batch_compute_behavioral_states
    
    users = get_all_users()
    if not users:
        return {'score': 100, 'label': 'NOMINAL', 'color': 'teal'}
        
    batch_states = batch_compute_behavioral_states()
    
    state_weights = {
        'STABLE': 100,
        'RECOVERING': 85,
        'DRIFTING': 45,
        'HIGH_RISK': 15,
        'UNKNOWN': 50
    }
    
    total_score = 0
    state_counts = {'STABLE': 0, 'DRIFTING': 0, 'HIGH_RISK': 0, 'RECOVERING': 0}
    
    if not batch_states or not isinstance(batch_states, dict):
        batch_states = {}

    for u in users:
        user_id = u['id']
        state_data = batch_states.get(user_id, {}) if batch_states else {}
        state = state_data.get('state', 'UNKNOWN')
        total_score += state_weights.get(state, 50)
        if state in state_counts:
            state_counts[state] += 1
            
    avg_score = round(total_score / len(users), 2)
    
    label = 'NOMINAL'
    color = 'teal'
    if avg_score < 40:
        label = 'CRITICAL'
        color = 'red'
    elif avg_score < 70:
        label = 'FRAGILE'
        color = 'amber'
        
    result = {
        'score': avg_score,
        'label': label,
        'status': label, # For cognitive summary
        'color': color,
        'metrics': state_counts, # Added for verification and summary
        'counts': state_counts,
        'user_count': len(users)
    }
    
    with _cache_lock:
        _systemic_cache['tri'] = {'data': result, 'expires': now + CACHE_TTL}
        
    return result


def detect_behavioral_contagion() -> dict:
    """
    Analyzes workforce aggregate to detect drift clustering.
    Governance Level D+: Systemic Synchronization Monitoring.
    """
    global _systemic_cache
    now = time.time()
    
    with _cache_lock:
        if _systemic_cache['contagion']['data'] and now < _systemic_cache['contagion']['expires']:
            return _systemic_cache['contagion']['data']

    from repository.db import execute_query
    
    # Try to fetch from persistent snapshot first (stricter cache)
    health_snapshot = execute_query(
        "SELECT snapshot_json FROM system_health_snapshots WHERE created_at > NOW() - INTERVAL '1 hour' ORDER BY created_at DESC LIMIT 1",
        fetch=True
    )
    if health_snapshot:
        result = health_snapshot[0]['snapshot_json']
        with _cache_lock:
            _systemic_cache['contagion'] = {'data': result, 'expires': now + 300}
        return result

    from repository.users_repo import get_all_users
    from services.user_service import batch_compute_behavioral_states
    
    users = get_all_users()
    if not users:
        return {"contagion_level": "None", "drift_rate": 0, "alert_triggered": False}

    batch_states = batch_compute_behavioral_states()
    drifting_users = []
    
    for u in users:
        user_id = u['id']
        state_data = batch_states.get(user_id, {})
        if state_data.get('state') in ('DRIFTING', 'HIGH_RISK'):
            drifting_users.append({
                'id': user_id,
                'name': u['full_name'],
                'state': state_data['state'],
                'z_score': state_data.get('z_score', 0)
            })
            
    total_observed = len(users)
    drifting_count = len(drifting_users)
    drift_rate = drifting_count / total_observed if total_observed > 0 else 0
            
    # --- Elite Level D: Population Z-Score Monitoring ---
    from repository.db import execute_query
    pop_stats = execute_query("SELECT AVG(avg_avoidance) as mean, STDDEV(avg_avoidance) as std FROM user_analytics_summary", fetch=True)
    
    # If no aggregate data, fallback to reasonable empirical defaults (but clearly labeled)
    expected_mean = (float(pop_stats[0]['mean']) / 100.0) if pop_stats and pop_stats[0]['mean'] else 0.10
    expected_std  = (float(pop_stats[0]['std']) / 100.0)  if pop_stats and pop_stats[0]['std']  else 0.05
    expected_std  = max(0.01, expected_std) # Epsilon gate for stability
    
    z_pop = (drift_rate - expected_mean) / expected_std
    alert_triggered = z_pop > 2.0 # Statistically significant synchronization
    
    result = {
        "contagion_level": "Critical" if z_pop > 3.0 else ("Elevated" if z_pop > 1.5 else "Nominal"),
        "drift_rate": round(drift_rate * 100, 1),
        "population_z": round(z_pop, 2),
        "population_size": total_observed,
        "affected_count": drifting_count,
        "alert_triggered": alert_triggered,
        "affected_users": drifting_users[:5],
        "recommendation": "Initiate pulse survey or systemic review." if alert_triggered else "No intervention required."
    }
    
    with _cache_lock:
        _systemic_cache['contagion'] = {'data': result, 'expires': now + CACHE_TTL}
        
    return result

