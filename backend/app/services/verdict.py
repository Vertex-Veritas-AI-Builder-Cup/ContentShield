"""Content-match risk labels and normalized public similarity scores."""

from __future__ import annotations

import math

HIGH_RISK_THRESHOLD = 0.75
MEDIUM_RISK_THRESHOLD = 0.50
CONTENT_SCORE_CENTER = 0.60
CONTENT_SCORE_SLOPE = 12.0
CONTENT_SCORE_FLOOR_PERCENT = 60.0
CONTENT_SCORE_CEILING_PERCENT = 100.0


def content_score_from_cosine(similarity: float) -> float:
    """Map raw cosine similarity to a bounded relative score in the 0-1 range.

    The logistic transform estimates the old public percentage, then the
    requested 60-100 window is stretched across the full display range.
    """

    bounded = max(-1.0, min(1.0, float(similarity)))
    logistic_percent = 100.0 / (
        1.0 + math.exp(-CONTENT_SCORE_SLOPE * (bounded - CONTENT_SCORE_CENTER))
    )
    normalized_percent = (
        (logistic_percent - CONTENT_SCORE_FLOOR_PERCENT)
        / (CONTENT_SCORE_CEILING_PERCENT - CONTENT_SCORE_FLOOR_PERCENT)
        * 100.0
    )
    return round(max(0.0, min(1.0, normalized_percent / 100.0)), 4)


def verdict_from_score(similarity: float) -> str:
    """Map the raw cosine-similarity score to the public risk category."""

    if similarity >= HIGH_RISK_THRESHOLD:
        return "high_risk"
    if similarity >= MEDIUM_RISK_THRESHOLD:
        return "medium_risk"
    return "low_risk"
