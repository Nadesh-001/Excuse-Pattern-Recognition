"""
AI Insights Generator — rule-based interpretation of analytics and AI signals.
"""
from dataclasses import dataclass, asdict


# ---------------------------------------------------------------------------
# Thresholds — all business rules live here, nowhere else.
# ---------------------------------------------------------------------------

class RiskThresholds:
    HIGH_RISK_CRITICAL_PCT = 40   # % of high-risk entries → critical
    HIGH_RISK_WARNING_PCT  = 20   # % of high-risk entries → warning

class AuthThresholds:
    LOW  = 50
    HIGH = 75

class AvoidThresholds:
    HIGH_AVOIDANCE = 40  # below this → critical (inverted scale)

class DelayThresholds:
    CRITICAL = 50
    WARNING  = 30

class WRSThresholds:
    LOW  = 50
    HIGH = 75

class TrustThresholds:
    LOW = 50


# ---------------------------------------------------------------------------
# Insight shape — enforced by dataclass, not ad-hoc dicts.
# ---------------------------------------------------------------------------

SEVERITY_CRITICAL = "critical"
SEVERITY_WARNING  = "warning"
SEVERITY_STABLE   = "stable"

VALID_SEVERITIES = {SEVERITY_CRITICAL, SEVERITY_WARNING, SEVERITY_STABLE}

@dataclass
class Insight:
    text: str
    severity: str
    category: str

    def __post_init__(self):
        if self.severity not in VALID_SEVERITIES:
            raise ValueError(f"Invalid severity '{self.severity}'. Must be one of {VALID_SEVERITIES}")

    def to_dict(self) -> dict:
        return asdict(self)


# ---------------------------------------------------------------------------
# Insight generators — one function per logical domain.
# ---------------------------------------------------------------------------

def _risk_insights(risk_dist: dict) -> list[Insight]:
    total = sum(risk_dist.values())
    if not total:
        return []
    pct = (risk_dist.get("High", 0) / total) * 100
    
    msgs = [
        "⚠️ High proportion of critical delay risks detected.",
        "⚠️ Critical risk levels observed in recent patterns.",
        "⚠️ Immediate attention required: High risk delays surging.",
        "⚡ Moderate risk exposure across team.",
        "⚡ Risk levels are elevated; monitoring advised.",
        "⚡ Emerging high-risk patterns detected.",
        "✅ Team risk levels are relatively stable.",
        "✅ Risk distribution remains within healthy limits.",
        "✅ No significant risk escalations detected."
    ]
    
    idx = int(pct) % len(msgs)
    if pct > RiskThresholds.HIGH_RISK_CRITICAL_PCT:
        return [Insight(msgs[idx], SEVERITY_CRITICAL, "risk")]
    if pct > RiskThresholds.HIGH_RISK_WARNING_PCT:
        return [Insight(msgs[idx], SEVERITY_WARNING, "risk")]
    
    return [Insight(msgs[idx], SEVERITY_STABLE, "risk")]


def _auth_insights(avg_auth: float) -> list[Insight]:
    msgs = [
        "🔍 Low authenticity trend detected in delay reasons.",
        "🔍 Explanation credibility is trending downward.",
        "🔍 Authenticity markers are below optimal range.",
        "✨ Strong authenticity pattern across team delays.",
        "✨ Credible and transparent communication detected.",
        "✨ High trust markers in recent submissions."
    ]
    idx = int(avg_auth) % len(msgs)
    if avg_auth < AuthThresholds.LOW:
        return [Insight(msgs[idx], SEVERITY_WARNING, "authenticity")]
    if avg_auth > AuthThresholds.HIGH:
        return [Insight(msgs[idx], SEVERITY_STABLE, "authenticity")]
    return []


def _avoidance_insights(avg_avoid: float) -> list[Insight]:
    msgs = [
        "⚠️ High avoidance behavior detected in team.",
        "⚠️ Avoidance patterns suggest underlying issues.",
        "⚠️ Team engagement metrics show avoidance signals."
    ]
    idx = int(avg_avoid) % len(msgs)
    if avg_avoid < AvoidThresholds.HIGH_AVOIDANCE:
        return [Insight(msgs[idx], SEVERITY_CRITICAL, "avoidance")]
    return []


def _delay_insights(delay_rate: float) -> list[Insight]:
    msgs = [
        "📊 Significant delay rate requires attention.",
        "📊 Delay frequency has reached critical levels.",
        "📊 Workflow momentum impacted by frequent delays.",
        "📈 Moderate delay frequency observed.",
        "📈 Delay patterns are emerging; keep watch.",
        "📈 Efficiency slightly impacting by moderate delays."
    ]
    idx = int(delay_rate) % len(msgs)
    if delay_rate > DelayThresholds.CRITICAL:
        return [Insight(msgs[idx], SEVERITY_CRITICAL, "delays")]
    if delay_rate > DelayThresholds.WARNING:
        return [Insight(msgs[idx], SEVERITY_WARNING, "delays")]
    return []


def _ai_insights(ai_data: dict) -> list[Insight]:
    results = []

    excuse_ai = ai_data.get("excuse_ai", {})
    if excuse_ai.get("repetition_flag"):
        sim = excuse_ai.get("similarity_score", 0)
        results.append(Insight(
            f"🤖 Repeated excuse patterns identified using NLP similarity ({sim * 100:.1f}%).",
            SEVERITY_WARNING, "ai_nlp"
        ))

    prediction_ai = ai_data.get("prediction_ai", {})
    if prediction_ai.get("risk_flag") == "High":
        prob = prediction_ai.get("delay_probability", 0)
        results.append(Insight(
            f"🔮 AI predicts high probability of future delays ({prob * 100:.1f}%).",
            SEVERITY_CRITICAL, "ai_prediction"
        ))

    anomaly_ai = ai_data.get("anomaly_ai", {})
    if anomaly_ai.get("anomaly_flag"):
        results.append(Insight(
            "🚨 Behavioral anomaly detected in recent activity.",
            SEVERITY_CRITICAL, "ai_anomaly"
        ))

    time_decay_ai = ai_data.get("time_decay_ai", {})
    weighted_score = time_decay_ai.get("weighted_trust_score", 0)
    if weighted_score < TrustThresholds.LOW:
        results.append(Insight(
            f"⏰ Recent behavior shows declining trust (weighted score: {weighted_score:.1f}).",
            SEVERITY_WARNING, "ai_trust"
        ))

    wrs_ai = ai_data.get("wrs_ai", {})
    wrs = wrs_ai.get("wrs_score", 0) if isinstance(wrs_ai, dict) else ai_data.get("intel_score", 0)
    
    if wrs < WRSThresholds.LOW:
        results.append(Insight(
            f"📉 Low behavioral reliability score detected (WRS: {wrs:.1f}).",
            SEVERITY_CRITICAL, "ai_wrs"
        ))
    elif wrs > WRSThresholds.HIGH:
        results.append(Insight(
            f"⭐ Excellent behavioral reliability score (WRS: {wrs:.1f}).",
            SEVERITY_STABLE, "ai_wrs"
        ))

    # New Light AI Insights (Behavioral Momentum Engine Tier 2)
    momentum_sig = ai_data.get("momentum_signals", {})
    
    # 1. Risk Spiral
    if momentum_sig.get("escalation_velocity") == "spiral":
        results.append(Insight(
            "🔥 Behavioral spiral detected: Risk scores are strictly increasing across consecutive entries.",
            SEVERITY_CRITICAL, "ai_momentum"
        ))
    
    # 2. Risk Drift
    drift_val = momentum_sig.get("risk_drift", 0)
    if drift_val > 8:
        results.append(Insight(
            f"📈 Rapid risk deterioration: 30-day average has surged +{drift_val} above the lifetime baseline.",
            SEVERITY_CRITICAL, "ai_momentum"
        ))
    elif drift_val > 4:
        results.append(Insight(
            "⚠️ Moderate upward risk trend observed in recent weeks.",
            SEVERITY_WARNING, "ai_momentum"
        ))
    
    # 3. Deadline Clustering
    burst = momentum_sig.get("deadline_burst", 0)
    if burst > 3:
        results.append(Insight(
            f"📦 High Deadline Clustering: {burst} delays submitted in 14 days suggests short-term workflow collapse.",
            SEVERITY_CRITICAL, "ai_momentum"
        ))

    # Legacy Momentum compatibility
    momentum_legacy = ai_data.get("momentum_ai", {}).get("risk_momentum", "Stable")
    if momentum_legacy == "Escalating" and not momentum_sig:
        results.append(Insight("🔥 Risk momentum escalating — proactive management advised.", SEVERITY_CRITICAL, "ai_momentum"))

    # Phase 3: Manipulation Resistance Flags
    manip_flags = ai_data.get("manipulation_flags", [])
    if "RECYCLED_EVIDENCE" in manip_flags:
        results.append(Insight(
            "🛑 Recycled Evidence Detected: This proof file has been used in previous delay submissions.",
            SEVERITY_CRITICAL, "ai_manipulation"
        ))
    if "STRUCTURAL_REPETITION" in manip_flags:
        results.append(Insight(
            "🧩 Template Gaming Detected: The sentence structure is identical to previous excuses, indicating a recycled template.",
            SEVERITY_CRITICAL, "ai_manipulation"
        ))
    elif "LOW_ENTROPY_EXCUSE" in manip_flags:
        results.append(Insight(
            "📝 Highly formulaic response: Low-entropy text suggests auto-generated or repetitive content.",
            SEVERITY_WARNING, "ai_manipulation"
        ))



    drift = ai_data.get("drift_ai", {})
    if drift.get("drift"):
        results.append(Insight(f"🚨 Behavioral drift detected: authenticity dropped by {drift.get('drop_magnitude')}% recently.", SEVERITY_CRITICAL, "ai_drift"))

    quality = ai_data.get("quality_ai", {})
    if quality.get("quality_label") == "High Generic":
        results.append(Insight(f"📝 High generic excuse ratio detected ({quality.get('generic_ratio')}%). Potential avoidance pattern.", SEVERITY_WARNING, "ai_quality"))

    return results


def _managerial_prescriptions(role: str, ai_data: dict) -> list[Insight]:
    """Tier 5: Prescriptive AI. Suggests clear actions for managers."""
    if role not in ('admin', 'manager'):
        return []
        
    results = []
    
    # 1. Adaptive Rebalancing
    b_state = ai_data.get("behavioral_state", {}).get("state", "STABLE")
    if b_state in ('HIGH_RISK', 'DRIFTING'):
        results.append(Insight(
            "🧠 ADAPTIVE REBALANCING: User is in a volatile state. Suggest reallocating upcoming high-complexity tasks to peers.",
            SEVERITY_WARNING, "prescription"
        ))
        
    # 2. Burnout Intervention
    tri = ai_data.get("team_resilience", {}).get("score", 100)
    if tri < 60:
        results.append(Insight(
            "🛑 BURNOUT INTERVENTION: Team resilience is critical. Suggest implementing a light-duty cycle or 1nday 'Deep Work' freeze.",
            SEVERITY_CRITICAL, "prescription"
        ))
        
    return results


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate_ai_insights(analytics_data: dict, ai_data: dict, role: str = "employee") -> list[dict]:
    """
    Generate insights from analytics and AI signals.

    Returns a list of plain dicts (not Insight objects) so callers and
    templates don't need to know about the internal dataclass.
    """
    insights: list[Insight] = []
    insights += _risk_insights(analytics_data.get("risk_distribution", {}))
    insights += _auth_insights(analytics_data.get("avg_auth_score", 0))
    insights += _avoidance_insights(analytics_data.get("avg_avoidance_score", 0))
    insights += _delay_insights(analytics_data.get("delay_rate", 0))
    if ai_data:
        insights += _ai_insights(ai_data)
        insights += _managerial_prescriptions(role, ai_data)

    if not insights:
        insights.append(Insight("✅ All metrics within normal ranges.", SEVERITY_STABLE, "general"))

    return [i.to_dict() for i in insights]


def generate_executive_summary(role: str, analytics_data: dict, ai_data: dict) -> str:
    """
    Generate a role-appropriate executive summary paragraph.

    Sentences are collected into a list and joined, so each conditional
    branch is independently readable and there's no string mutation.
    """
    risk_dist  = analytics_data.get("risk_distribution", {})
    avg_auth   = analytics_data.get("avg_auth_score", 0)
    avg_avoid  = analytics_data.get("avg_avoidance_score", 0)
    delay_rate = analytics_data.get("delay_rate", 0)

    high_risk   = risk_dist.get("High", 0)
    medium_risk = risk_dist.get("Medium", 0)

    prediction_ai   = (ai_data or {}).get("prediction_ai", {})
    prediction_prob = prediction_ai.get("delay_probability", 0)
    prediction_flag = "High" if prediction_prob > 40 else "Low" # Simple threshold for summary
    
    drift_ai = (ai_data or {}).get("drift_ai", {})
    drift_flag = drift_ai.get("drift", False)
    
    momentum_ai = (ai_data or {}).get("momentum_ai", {})
    momentum_level = momentum_ai.get("risk_momentum", "Stable")
    
    repetition_flag  = (ai_data or {}).get("excuse_ai", {}).get("repetition_penalty", 0) > 10
    wrs_score        = (ai_data or {}).get("intel_score", 0)


    sentences: list[str] = []

    if role == "admin":
        sentences.append(
            f"The team currently shows {high_risk} high-risk and "
            f"{medium_risk} medium-risk delays, with an authenticity average of {avg_auth:.1f}%."
        )
        if momentum_level == "Escalating":
            sentences.append("Risk momentum is currently ESCALATING.")
        if drift_flag:
            sentences.append("A significant behavioral drift has been detected in recent team behavior.")
        if prediction_flag == "High":
            sentences.append(f"AI predicts a high probability ({prediction_prob * 100:.1f}%) of future delays across upcoming tasks.")
        elif wrs_score < WRSThresholds.LOW:
            sentences.append("Overall reliability score indicates declining team performance.")
        else:
            sentences.append("Team stability appears within acceptable thresholds.")
        if repetition_flag:
            sentences.append("Repeated excuse patterns detected across submissions.")

    elif role == "manager":
        sentences.append(
            f"The team delay rate is {delay_rate:.1f}%, with "
            f"{medium_risk + high_risk} moderate-to-high risk cases."
        )
        if avg_auth < AuthThresholds.HIGH:
            sentences.append("Authenticity trends require monitoring.")
        else:
            sentences.append("Authenticity trends remain strong.")
        if prediction_flag == "High":
            sentences.append("AI indicates increased risk for future delays.")
        if drift_flag:
            sentences.append("Unusual behavioral patterns detected in team activity.")
        if avg_avoid < AvoidThresholds.HIGH_AVOIDANCE:
            sentences.append("High avoidance behavior observed.")

    elif role == "employee":
        sentences.append(
            f"Your current delay rate is {delay_rate:.1f}% with {high_risk} high-risk submissions."
        )
        if repetition_flag:
            sentences.append("Repeated excuse patterns have been detected.")
        if (ai_data or {}).get("anomaly_ai", {}).get("anomaly_flag"):
            sentences.append("Recent activity shows unusual behavioral patterns.")
        if prediction_flag == "High":
            sentences.append(f"AI predicts higher delay risk ({prediction_prob * 100:.1f}%) for your upcoming tasks.")
        if avg_auth > AuthThresholds.HIGH:
            sentences.append("Overall credibility remains strong.")
        elif avg_auth < AuthThresholds.LOW:
            sentences.append("Consider improving submission authenticity to build trust.")
        if wrs_score > WRSThresholds.HIGH:
            sentences.append("Your behavioral reliability score is excellent.")

    # Tier 5: Prescriptive Executive Sentiment
    prescriptions = _managerial_prescriptions(role, ai_data or {})
    if prescriptions:
        sentences.append(f"AI Prescription: {prescriptions[0].text}")

    return " ".join(sentences) if sentences else "Insufficient data for executive summary."
