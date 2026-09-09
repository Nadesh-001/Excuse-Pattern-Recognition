import re
from typing import List, Dict, Any

# STOP_WORDS could be expanded, but keeping minimal for now

# STOP_WORDS could be expanded, but keeping minimal for now
STOP_WORDS = set(['the', 'and', 'is', 'in', 'at', 'of', 'on', 'for', 'to', 'a', 'an'])

# --- FREE-TIER OPTIMIZATION: Singleton ML Lazy Loaders ---
_sklearn = None
_textblob = None

def _get_sklearn():
    global _sklearn
    if _sklearn is None:
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.metrics.pairwise import cosine_similarity
        from sklearn.cluster import MiniBatchKMeans
        import numpy as np
        _sklearn = {
            'TfidfVectorizer': TfidfVectorizer,
            'cosine_similarity': cosine_similarity,
            'MiniBatchKMeans': MiniBatchKMeans,
            'np': np
        }
    return _sklearn

def _get_textblob():
    global _textblob
    if _textblob is None:
        from textblob import TextBlob
        _textblob = TextBlob
    return _textblob

def check_excuse_history(new_excuse: str, past_excuses: List[str]) -> float:
    """
    Checks if the current excuse is a reworded version of an old one.
    Returns a similarity score between 0.0 and 1.0 using TF-IDF.
    """
    if not past_excuses:
        return 0.0
    
    # Clean and filter empty excuses
    valid_past = [e for e in past_excuses if e and e.strip()]
    if not valid_past:
        return 0.0

    sk = _get_sklearn()
    TfidfVectorizer = sk['TfidfVectorizer']
    cosine_similarity = sk['cosine_similarity']

    vectorizer = TfidfVectorizer()
    all_text = [new_excuse] + valid_past
    
    try:
        tfidf = vectorizer.fit_transform(all_text)
        # Compare new excuse (index 0) with all past ones
        similarities = cosine_similarity(tfidf[0:1], tfidf[1:])
        return float(max(similarities[0]))
    except Exception as e:
        print(f"Similarity Engine Error: {e}")
        return 0.0

def extract_blocker_entities(text: str) -> Dict[str, List[str]]:
    """
    Extracts Entities (People, Tools, Dates) from the excuse text using lightweight heuristics/regex.
    """
    text_lower = text.lower()
    
    entities = {
        "PERSON": [], 
        "GPE": [],    
        "DATE": re.findall(r'\b(?:\\d{1,2}[/-]\\d{1,2}[/-]\\d{2,4}|today|tomorrow|yesterday|monday|tuesday|wednesday|thursday|friday|saturday|sunday)\\b', text_lower),
        "ORG": [],
        "PRODUCT": []
    }
    
    # Simple capitalized word extraction (very rough heuristic for names/proper nouns)
    words = text.split()
    potential_names = []
    for i, word in enumerate(words):
        # Clean punctuation
        word_clean = word.strip(".,!?\"'")
        if i > 0 and word_clean and word_clean[0].isupper() and word_clean.lower() not in STOP_WORDS:
            potential_names.append(word_clean)
            
    if potential_names:
        # Assign to PERSON for now as a generic catch-all for proper nouns
        entities["PERSON"] = potential_names
        
    return entities
def analyze_excuse_sentiment(text: str) -> Dict[str, Any]:
    """
    Analyzes the sentiment and subjectivity of the excuse.
    High subjectivity often correlates with internal rationalizations.
    """
    TextBlob = _get_textblob()
    blob = TextBlob(text)
    sentiment = blob.sentiment
    return {
        "polarity": float(sentiment.polarity),      # -1.0 to 1.0 (negative to positive)
        "subjectivity": float(sentiment.subjectivity), # 0.0 to 1.0 (objective to subjective)
        "assessment": "Subjective" if sentiment.subjectivity > 0.5 else "Objective"
    }

def suggest_task_attributes(title: str, description: str = "") -> Dict[str, str]:
    """
    Lightweight heuristic to suggest priority and category based on keywords.
    """
    combined = (title + " " + description).lower()
    
    # Priority Heuristics
    priority = "Medium"
    high_keywords = ['urgent', 'asap', 'critical', 'blocker', 'immediately', 'fix', 'broken', 'emergency']
    low_keywords = ['routine', 'optional', 'backlog', 'someday', 'experimental', 'minor']
    
    if any(k in combined for k in high_keywords):
        priority = "High"
    elif any(k in combined for k in low_keywords):
        priority = "Low"
        
    # Category Heuristics
    category = "General"
    mapping = {
        "Technical": ['refactor', 'bug', 'code', 'deploy', 'api', 'database', 'frontend', 'backend', 'fix', 'develop'],
        "Logistics": ['meeting', 'call', 'review', 'email', 'organize', 'schedule', 'planning'],
        "Analysis": ['research', 'audit', 'study', 'graph', 'data', 'metrics', 'evaluate'],
        "Design": ['ui', 'ux', 'css', 'style', 'prototype', 'mockup', 'visual']
    }
    
    for cat, keys in mapping.items():
        if any(k in combined for k in keys):
            category = cat
            break
            
    return {
        "suggested_priority": priority,
        "suggested_category": category
    }

# ---------------------------------------------------------------------------
# Phase 2: Cognitive Pattern Detection (Advanced Behavioral Intelligence)
# ---------------------------------------------------------------------------

def analyze_hedging_and_defensiveness(text: str) -> dict:
    """
    Detects hedging words and defensive language patterns.
    High score indicates potential rationalization or lack of confidence.
    """
    if not text:
        return {"score": 0, "matrix": [], "label": "Direct"}

    text_lower = text.lower()
    words = text_lower.split()
    total_words = len(words)
    if total_words == 0:
        return {"score": 0, "matrix": [], "label": "Direct"}

    # Hedging / Uncertainty keywords
    HEDGING_TERMS = [
        "maybe", "perhaps", "possibly", "might", "could", "think", "guess", 
        "believe", "assume", "probably", "unsure", "unclear", "seems"
    ]
    
    # Defensive / Justification keywords
    DEFENSIVE_TERMS = [
        "just", "actually", "basically", "simply", "honestly", "really", 
        "literally", "technically", "obviously", "try", "tried"
    ]

    hedge_hits = [w for w in words if w in HEDGING_TERMS]
    defensive_hits = [w for w in words if w in DEFENSIVE_TERMS]
    
    hedge_count = len(hedge_hits)
    defensive_count = len(defensive_hits)
    
    # Scoring normalized to 0-100 (approximately)
    # 1 hedge per 10 words is high frequency.
    raw_score = ((hedge_count * 1.5) + (defensive_count * 1.0)) / total_words * 100
    final_score = min(round(raw_score * 2.5), 100) # multiplier to scale it up

    label = "Direct"
    if final_score > 60:
        label = "Defensive/Uncertain"
    elif final_score > 30:
        label = "Guarded"

    return {
        "score": final_score,
        "hedging_count": hedge_count,
        "defensive_count": defensive_count,
        "label": label,
        "matrix": list(set(hedge_hits + defensive_hits))[:5]
    }

def calculate_over_explanation_score(text: str, subjectivity: float) -> dict:
    """
    Combines text length and subjectivity to detect over-explanation.
    Long text + High Subjectivity = High Over-Explanation Risk.
    """
    if not text:
        return {"score": 0, "label": "Concise"}

    word_count = len(text.split())
    
    # Length Component (0-50)
    # Sweet spot is usually 10-30 words. >50 starts getting suspicious if subjective.
    length_score = min(max((word_count - 20) * 1.5, 0), 50)
    
    # Subjectivity Component (0-50)
    # subjectivity is 0.0 to 1.0
    subjectivity_score = subjectivity * 50

    total_score = round(length_score + subjectivity_score)
    
    label = "Concise"
    if total_score > 75:
        label = "Over-Explained"
    elif total_score > 40:
        label = "Verbose"

    return {
        "score": min(total_score, 100),
        "word_count": word_count,
        "label": label
    }

def check_consistency_variance(current_text: str, past_texts: list[str]) -> dict:
    """
    Checks for contradictions or repeating patterns against recent history.
    Uses simple keyword overlap variance and sentiment flips (if extended).
    Currently focuses on 'Keyword Recycling' for consistency checking.
    """
    if not current_text or not past_texts:
        return {"score": 100, "status": "Consistent"} # Default trust

    current_words = set(re.findall(r'\b\w+\b', current_text.lower())) - STOP_WORDS
    if not current_words:
        return {"score": 100, "status": "Consistent"}

    overlap_counts = []
    for past in past_texts:
        if not past: continue
        past_words = set(re.findall(r'\b\w+\b', past.lower())) - STOP_WORDS
        overlap = len(current_words.intersection(past_words))
        overlap_counts.append(overlap)
    
    # Analyze overlap
    # If overlap is very high with ONE specific past excuse -> Copy Paste Risk
    # If overlap is constantly high across ALL -> Repetitive Behavior
    
    max_overlap = max(overlap_counts) if overlap_counts else 0
    avg_overlap = sum(overlap_counts) / len(overlap_counts) if overlap_counts else 0
    
    # Consistency Score (100 = Unique/Fresh, 0 = Exact Copy)
    # 5 words overlap is significant for short texts
    penalty = (max_overlap * 10) + (avg_overlap * 5)
    consistency_score = max(0, 100 - round(penalty))

    status = "Unique"
    if consistency_score < 40:
        status = "Highly Repetitive"
    elif consistency_score < 70:
        status = "Recurring Themes"

    return {
        "score": consistency_score,
        "status": status,
        "max_overlap_words": max_overlap
    }

def cluster_excuse_patterns(excuses: list[str]) -> dict:
    """
    Groups excuses into clusters to identify recurring themes (e.g., "Health", "Technical", "Vague").
    Uses MiniBatchKMeans for speed and low memory usage.
    """
    if not excuses or len(excuses) < 3:
        return {"clusters": [], "dominant_theme": "Insufficient Data"}

    try:
        sk = _get_sklearn()
        TfidfVectorizer = sk['TfidfVectorizer']
        MiniBatchKMeans = sk['MiniBatchKMeans']
        np = sk['np']

        # Vectorize
        vectorizer = TfidfVectorizer(stop_words='english', max_features=50)
        X = vectorizer.fit_transform(excuses)
        
        # Cluster (Dynamic k based on data size, max 3)
        n_clusters = min(3, len(excuses))
        kmeans = MiniBatchKMeans(n_clusters=n_clusters, random_state=42, batch_size=10, n_init="auto")
        kmeans.fit(X)
        
        # Analyze clusters
        feature_names = vectorizer.get_feature_names_out()
        cluster_info = []
        
        # Get top terms per cluster
        ordered_centroids = kmeans.cluster_centers_.argsort()[:, ::-1]
        
        for i in range(n_clusters):
            top_indices = ordered_centroids[i, :3] # Top 3 keywords
            keywords = [feature_names[ind] for ind in top_indices]
            
            # Count items in this cluster
            count = np.sum(kmeans.labels_ == i)
            
            cluster_info.append({
                "cluster_id": int(i),
                "keywords": keywords,
                "count": int(count),
                "ratio": round(int(count) / len(excuses) * 100, 1)
            })
            
        # Sort by size
        cluster_info.sort(key=lambda x: x['count'], reverse=True)
        dominant = cluster_info[0]['keywords'] if cluster_info else []
        
        return {
            "clusters": cluster_info,
            "dominant_keywords": dominant,
            "pattern_detected": cluster_info[0]['ratio'] > 50 # If one cluster is >50%, it's a strong pattern
        }
        
    except Exception as e:
        print(f"Clustering Error: {e}")
        return {"clusters": [], "dominant_theme": "Error"}

def calculate_text_entropy(text: str) -> float:

    """
    Calculates the Shannon entropy of word frequencies in an excuse.
    Low entropy (< 3.0) indicates repetitive, formulaic, or low-effort text.
    """
    import math
    from collections import Counter
    
    if not text or len(text.split()) < 3:
        return 0.0

    words = re.findall(r'\b\w+\b', text.lower())
    counts = Counter(words)
    total = len(words)
    
    entropy = 0.0
    for count in counts.values():
        p = count / total
        entropy -= p * math.log2(p)
    
    return round(entropy, 2)

def detect_structural_skeleton(text: str) -> str:
    """
    Reduces an excuse to its structural skeleton (POS template-like).
    Replaces all non-stop words with generic placeholders based on length.
    Helps identify 'The Template User' who reuses the same sentence structure.
    """
    if not text:
        return ""
        
    words = text.lower().split()
    skeleton = []
    
    for w in words:
        clean_w = re.sub(r'[^\w]', '', w)
        if clean_w in STOP_WORDS or len(clean_w) <= 2:
            skeleton.append(w)
        else:
            # Replace substantive words with a length-based token
            skeleton.append(f"X{len(clean_w)}") 
            
    return " ".join(skeleton)


# ---------------------------------------------------------------------------
# Phase 3: Real / Fake Verdict Classifier
# ---------------------------------------------------------------------------

def classify_excuse_verdict(signals: dict) -> dict:
    """
    Produces a binary-plus verdict: REAL, SUSPICIOUS, or FAKE.

    Signals expected in the input dict:
      - similarity_score   (float 0-1): cosine similarity to past excuses
      - hedging_score      (float 0-100): linguistic hedging / defensiveness
      - entropy_score      (float 0-100): low entropy = repetitive / template-like
      - sentiment_subjectivity (float 0-1): high subjectivity = rationalisation risk
      - ai_flags           (list[str]): flags from Groq AI e.g. ["generic_excuse", "vague_reason"]

    Returns:
      {
        "verdict": "REAL" | "SUSPICIOUS" | "FAKE",
        "fake_score": int (0-100),
        "verdict_reason": str
      }
    """
    fake_score = 0
    reasons = []

    # --- Signal 1: Copy-paste similarity to past excuses (0-30 pts) ---
    similarity = float(signals.get("similarity_score", 0.0))
    if similarity >= 0.85:
        fake_score += 30
        reasons.append("near-identical to a previous excuse")
    elif similarity >= 0.6:
        fake_score += 20
        reasons.append("highly similar to past excuses")
    elif similarity >= 0.4:
        fake_score += 10
        reasons.append("some overlap with prior excuses")

    # --- Signal 2: Hedging & defensive language (0-20 pts) ---
    hedging = float(signals.get("hedging_score", 0.0))
    if hedging >= 70:
        fake_score += 20
        reasons.append("very high hedging / defensive tone")
    elif hedging >= 45:
        fake_score += 10
        reasons.append("elevated hedging language detected")

    # --- Signal 3: Low entropy / templated structure (0-20 pts) ---
    entropy = float(signals.get("entropy_score", 0.0))
    if entropy >= 80:
        fake_score += 20
        reasons.append("formulaic / low-entropy text")
    elif entropy >= 60:
        fake_score += 10
        reasons.append("moderately repetitive sentence structure")

    # --- Signal 4: High subjectivity / emotional rationalisation (0-15 pts) ---
    subjectivity = float(signals.get("sentiment_subjectivity", 0.0))
    if subjectivity >= 0.8:
        fake_score += 15
        reasons.append("extremely high emotional subjectivity")
    elif subjectivity >= 0.6:
        fake_score += 8
        reasons.append("subjective / personal rationalisation")

    # --- Signal 5: AI suspicion flags (0-15 pts) ---
    ai_flags = signals.get("ai_flags", []) or []
    if "generic_excuse" in ai_flags:
        fake_score += 10
        reasons.append("AI flagged as generic excuse")
    if "vague_reason" in ai_flags:
        fake_score += 5
        reasons.append("AI flagged as vague reason")
    if "contradictory" in ai_flags:
        fake_score += 7
        reasons.append("AI detected contradictory statements")

    # --- Clamp to 0-100 ---
    fake_score = min(100, max(0, int(fake_score)))

    # --- Verdict threshold ---
    if fake_score >= 50:
        verdict = "FAKE"
    elif fake_score >= 28:
        verdict = "SUSPICIOUS"
    else:
        verdict = "REAL"

    verdict_reason = "; ".join(reasons) if reasons else "No suspicious patterns detected"

    return {
        "verdict": verdict,
        "fake_score": fake_score,
        "verdict_reason": verdict_reason
    }
