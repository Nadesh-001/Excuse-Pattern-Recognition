"""
Deterministic Scoring Engine
=============================
Computes excuse authenticity and risk level from five weighted signals:

  Signal                  Weight
  ----------------------  ------
  Excuse text quality      30 %
  Delay history            20 %
  Task priority context    20 %
  Proof attachment         15 %
  Timing behaviour         15 %

An optional AI signal (0–15 pts) may be merged into the final score.
"""

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Thresholds — change business rules here, nowhere else.
# ---------------------------------------------------------------------------

THRESHOLD_LOW    = 75   # score >= this → risk LOW
THRESHOLD_MEDIUM = 45   # score >= this → risk MEDIUM (else HIGH)

_MAX_SCORE     = 100
_MAX_AI_SIGNAL = 15     # ceiling on external AI contribution

# ---------------------------------------------------------------------------
# Text quality signal
# ---------------------------------------------------------------------------

# Phrases are matched as substrings; see score_text_quality for caveats.
_GENERIC_PHRASES = frozenset([
    "not feeling well",
    "network issue",
    "personal reasons",
    "busy schedule",
    "unexpected work",
])

_TEXT_MAX          = 30
_SHORT_WORD_CUTOFF = 5
_MEDIUM_WORD_CUTOFF = 10
_SHORT_PENALTY     = 15
_MEDIUM_PENALTY    = 8
_GENERIC_PENALTY   = 5


def score_text_quality(reason: str) -> int:
    """
    Score excuse text quality out of 30.

    Penalises short responses and known generic phrases.
    Phrase matching is substring-based: a specific excuse that happens to
    contain a generic phrase will still be penalised. Each matched phrase
    applies one penalty (matching the same phrase twice does not double it).
    """
    if not reason:
        return 0

    normalised  = reason.lower()
    word_count  = len(normalised.split())
    score       = _TEXT_MAX

    if word_count < _SHORT_WORD_CUTOFF:
        score -= _SHORT_PENALTY
    elif word_count < _MEDIUM_WORD_CUTOFF:
        score -= _MEDIUM_PENALTY

    matched_phrases = {p for p in _GENERIC_PHRASES if p in normalised}
    score -= len(matched_phrases) * _GENERIC_PENALTY

    return max(score, 0)


# ---------------------------------------------------------------------------
# Delay history signal
# ---------------------------------------------------------------------------

def score_delay_history(delay_count: int) -> int:
    """Score delay history out of 20. More prior delays → lower score."""
    if delay_count <= 0:
        return 20
    if delay_count <= 2:
        return 14
    if delay_count <= 5:
        return 8
    return 3


# ---------------------------------------------------------------------------
# Task context signal
# ---------------------------------------------------------------------------

_PRIORITY_NORMALISE = {'high': 'High', 'medium': 'Medium', 'low': 'Low'}
_VALID_PRIORITIES   = frozenset(_PRIORITY_NORMALISE.values())


def score_task_context(priority: str, hours_left: int) -> int:
    """
    Score task priority and deadline context out of 20.

    High-priority tasks submitted within 12 hours of deadline receive a
    larger penalty than medium-priority tasks within 24 hours.
    Unknown or missing priority values are treated as Low (no deduction)
    and logged as a warning so data quality issues surface.
    """
    raw = (priority or '').strip()
    normalised_priority = _PRIORITY_NORMALISE.get(raw.lower())

    if raw and normalised_priority is None:
        logger.warning("score_task_context: unrecognised priority %r — treating as Low", raw)

    score = 20
    if normalised_priority == 'High' and hours_left < 12:
        score -= 12
    elif normalised_priority == 'Medium' and hours_left < 24:
        score -= 6

    return max(score, 0)


# ---------------------------------------------------------------------------
# Proof attachment signal
# ---------------------------------------------------------------------------

def score_proof_attachment(has_proof: bool) -> int:
    """Score proof attachment out of 15."""
    return 15 if has_proof else 5


# ---------------------------------------------------------------------------
# Timing signal
# ---------------------------------------------------------------------------

def score_timing(is_after_deadline: bool) -> int:
    """Score submission timing out of 15. Late submissions score lower."""
    return 5 if is_after_deadline else 15


# ---------------------------------------------------------------------------
# Composite scorer
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ScoreBreakdown:
    text:      int
    history:   int
    task:      int
    proof:     int
    timing:    int
    ai_signal: int
    total:     int
    risk:      str     # 'Low' | 'Medium' | 'High'
    verdict:   str     # 'REAL' | 'SUSPICIOUS' | 'FAKE'


# ---------------------------------------------------------------------------
# Verdict thresholds — single source of truth for REAL/SUSPICIOUS/FAKE
# ---------------------------------------------------------------------------

VERDICT_REAL       = 65   # authenticity >= this → REAL
VERDICT_SUSPICIOUS = 40   # authenticity >= this → SUSPICIOUS (else FAKE)


def calculate_authenticity_score(
    reason:            str,
    delay_count:       int,
    priority:          str,
    hours_left:        int,
    has_proof:         bool,
    is_after_deadline: bool,
    ai_score:          int = 0,
) -> ScoreBreakdown:
    """
    Compute a full authenticity score and risk classification.

    The ai_score parameter accepts the output of score_ai_signal()
    (0–15). It is clamped to [0, _MAX_AI_SIGNAL] before merging so a
    negative or oversized external signal cannot distort the result.
    """
    text    = score_text_quality(reason)
    history = score_delay_history(delay_count)
    task    = score_task_context(priority, hours_left)
    proof   = score_proof_attachment(has_proof)
    timing  = score_timing(is_after_deadline)

    clamped_ai = max(0, min(ai_score, _MAX_AI_SIGNAL))
    total      = min(text + history + task + proof + timing + clamped_ai, _MAX_SCORE)

    if total >= THRESHOLD_LOW:
        risk = 'Low'
    elif total >= THRESHOLD_MEDIUM:
        risk = 'Medium'
    else:
        risk = 'High'

    # --- Verdict classification (REAL / SUSPICIOUS / FAKE) ---
    if total >= VERDICT_REAL:
        verdict = 'REAL'
    elif total >= VERDICT_SUSPICIOUS:
        verdict = 'SUSPICIOUS'
    else:
        verdict = 'FAKE'

    return ScoreBreakdown(
        text=text, history=history, task=task,
        proof=proof, timing=timing, ai_signal=clamped_ai,
        total=total, risk=risk, verdict=verdict,
    )
