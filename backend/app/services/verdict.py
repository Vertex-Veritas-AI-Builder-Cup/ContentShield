"""Content-match risk labels and calibrated public similarity scores."""

from __future__ import annotations

import math

HIGH_RISK_THRESHOLD = 0.75
MEDIUM_RISK_THRESHOLD = 0.50
CONTENT_SCORE_CENTER = 0.60
CONTENT_SCORE_SLOPE = 12.0


def content_score_from_cosine(similarity: float) -> float:
    """Map raw cosine similarity to a bounded, monotonic 0-100 display score."""

    bounded = max(-1.0, min(1.0, float(similarity)))
    score = 100.0 / (1.0 + math.exp(-CONTENT_SCORE_SLOPE * (bounded - CONTENT_SCORE_CENTER)))
    return round(score, 2)


def verdict_from_score(similarity: float) -> str:
    """Map the raw cosine-similarity score to the public risk category."""

    if similarity >= HIGH_RISK_THRESHOLD:
        return "high_risk"
    if similarity >= MEDIUM_RISK_THRESHOLD:
        return "medium_risk"
    return "low_risk"
