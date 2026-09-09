from datetime import datetime
from typing import List, Dict, Any

from services.nlp_service import (
    analyze_hedging_and_defensiveness,
    calculate_text_entropy,
    analyze_excuse_sentiment
)

# Governance Constants
ENGINE_VERSION = "1.1"
WEIGHTS_V1 = {
    "delay_score": 0.35,
    "entropy_score": 0.20,
    "hedging_ratio": 0.15,
    "deadline_pressure": 0.15,
    "sentiment_penalty": 0.15
}

class TaskIntelligenceEngine:
    """
    Enterprise-grade Behavioral Analysis Engine.
    Handles deterministic feature extraction, risk scoring, and rule-based flags.
    Target: Governance Level C (Behavioral Modeling).
    """

    def __init__(self, user_id: int):
        self.user_id = user_id
        self.features = {}
        self.risk_score = 0.0
        self.flags = []

    def extract_features(self, text: str, delay_days: int, pressure: float, history: List[Dict[str, Any]]) -> Dict[str, float]:
        """
        Extracts deterministic behavioral features scaled 0-100.
        """
        # 1. Linguistic Analysis
        hedging = analyze_hedging_and_defensiveness(text)
        entropy = calculate_text_entropy(text)
        sentiment = analyze_excuse_sentiment(text)
        
        # 2. Scaling (Independent of AI)
        hedging_score = float(hedging.get('score', 0))
        
        # Entropy Mapping: Low entropy (<3.0) is higher risk. Max score at entropy=0.
        entropy_score = max(0.0, min(100.0, (5.0 - entropy) * 20.0))
        
        # Sentiment mapping: Negative polarity increases penalty (0-1).
        # We want 0-100. 1.0 (very negative) -> 100. 0.0 -> 0.
        sentiment_val = max(0.0, min(100.0, (1.0 - sentiment.get('polarity', 0)) * 50.0))

        # Delay Score: 10 points per day, capped at 100.
        delay_score = min(100.0, float(delay_days) * 10.0)
        
        # Pressure: already scaled 0-100 from repository/service layer
        pressure_score = min(100.0, float(pressure))

        self.features = {
            "delay_score": delay_score,
            "entropy_score": entropy_score,
            "hedging_ratio": hedging_score,
            "deadline_pressure": pressure_score,
            "sentiment_penalty": sentiment_val
        }
        return self.features

    def compute_task_risk(self) -> float:
        """
        Calculates risk using centrally defined WEIGHTS_V1.
        """
        if not self.features:
            return 0.0
            
        raw_total = sum(self.features[k] * WEIGHTS_V1[k] for k in WEIGHTS_V1 if k in self.features)
        self.risk_score = round(max(0.0, min(100.0, raw_total)), 2)
        return self.risk_score

    def trigger_flags(self) -> List[Dict[str, str]]:
        """
        Rule-based flag generation ONLY. No AI-driven decisions.
        """
        self.flags = []
        
        if self.features.get('delay_score', 0) > 50:
            self.flags.append({"label": "HIGH_DELAY_IMPACT", "severity": "red"})
        
        if self.features.get('hedging_ratio', 0) > 60:
            self.flags.append({"label": "ELEVATED_HEDGING", "severity": "orange"})
            
        if self.features.get('entropy_score', 0) > 75:
            self.flags.append({"label": "STRUCTURAL_REPETITION", "severity": "red"})
            
        if self.features.get('sentiment_penalty', 0) > 70:
            self.flags.append({"label": "DEFENSIVE_TONE", "severity": "orange"})
            
        return self.flags

    def compute_confidence(self, history_size: int) -> float:
        """
        Calculates score confidence based on history size and data maturity.
        Target: min(1.0, history / 10).
        """
        maturity_threshold = 10
        confidence = min(1.0, history_size / maturity_threshold)
        return round(confidence * 100.0, 1)

    def generate_snapshot(self, confidence: float, reliability_index: float = 0.0) -> Dict[str, Any]:
        """
        Generates an auditable snapshot of the intelligence state.
        """
        return {
            "engine_version": ENGINE_VERSION,
            "feature_vector": self.features,
            "risk_score": self.risk_score,
            "flags": self.flags,
            "confidence_score": confidence,
            "pressure": self.features.get("deadline_pressure", 0.0),
            "confidence": confidence,
            "reliability_index": reliability_index,
            "calculated_at": datetime.now().isoformat()
        }

# --- USER-LEVEL EVOLUTIONARY INTELLIGENCE (HARDENED) ---

def calculate_rolling_risk(prev_avg: float, current_task_risk: float) -> float:
    """EMA logic (v1.0): 0.8 / 0.2 split."""
    if prev_avg == 0: return current_task_risk
    return round(prev_avg * 0.8 + current_task_risk * 0.2, 1)

def calculate_kinematics(history: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Kinematic analysis (Velocity/Acceleration) Normalized by Time.
    history: List of {"score": float, "timestamp": datetime} ordered DESC.
    Governance Level D+: Quant-Grade Temporal Modeling.
    """
    if len(history) < 2:
        return {"risk_velocity": 0.0, "risk_acceleration": 0.0, "confidence": "LOW"}
    
    try:
        # 1. Calculate Velocity (v = Δrisk / Δtime)
        # We use days as the time unit for human-readable momentum
        h0, h1 = history[0], history[1]
        dt1 = (h0['timestamp'] - h1['timestamp']).total_seconds() / 86400.0 # days
        
        # If dt is near zero (simultaneous), we treat it as sequential with a min delta
        # to prevent division by zero, but velocity will be high.
        dt1 = max(0.01, dt1) 
        
        velocity = (h0['score'] - h1['score']) / dt1
        
        # 2. Calculate Acceleration (a = Δvelocity / Δtime)
        acceleration = 0.0
        if len(history) >= 3:
            h2 = history[2]
            dt2 = (h1['timestamp'] - h2['timestamp']).total_seconds() / 86400.0
            dt2 = max(0.01, dt2)
            
            prev_velocity = (h1['score'] - h2['score']) / dt2
            
            # --- EMA Smoothing (Quant-Grade Stability) ---
            # Alpha = 0.6 favors recent change but filters high-frequency noise
            alpha = 0.6
            velocity = (alpha * velocity) + ((1 - alpha) * prev_velocity)
            
            # Δv over the average interval
            avg_dt = (dt1 + dt2) / 2.0
            acceleration = (velocity - prev_velocity) / avg_dt
            
            # Smooth acceleration if possible
            if len(history) >= 4:
                h3 = history[3]
                dt3 = (h2['timestamp'] - h3['timestamp']).total_seconds() / 86400.0
                dt3 = max(0.01, dt3)
                old_v = (h2['score'] - h3['score']) / dt3
                old_acc = (prev_velocity - old_v) / ((dt2+dt3)/2)
                acceleration = (alpha * acceleration) + ((1 - alpha) * old_acc)
            
        return {
            "risk_velocity": round(velocity, 2),
            "risk_acceleration": round(acceleration, 2),
            "normalized_units": "risk_points_per_day",
            "confidence": "STABLE" if abs(velocity) < 10 else "VOLATILE"
        }
    except Exception:
        return {"risk_velocity": 0.0, "risk_acceleration": 0.0, "confidence": "ERROR"}

def calculate_integrity_index(metrics: Dict[str, float]) -> Dict[str, Any]:
    """Integrity formula: 0.4*manip + 0.3*vol + 0.3*entropy."""
    idx = (0.4 * metrics.get('manip_risk', 0) + 
           0.3 * metrics.get('volatility', 0) + 
           0.3 * metrics.get('entropy', 0))
    
    idx = max(0, min(100, idx))
    status = "SECURE" if idx < 30 else ("HIGH_RISK" if idx > 70 else "COMPROMISED")
    
    return {"score": round(idx, 1), "status": status}
