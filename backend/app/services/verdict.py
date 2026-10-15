"""Content-match risk labels and bounded public similarity scores."""

from __future__ import annotations

HIGH_RISK_THRESHOLD = 0.75
MEDIUM_RISK_THRESHOLD = 0.50


def content_score_from_cosine(similarity: float) -> float:
    """Keep a composite similarity score bounded in the 0-1 range."""

    bounded = max(-1.0, min(1.0, float(similarity)))
    return round(max(0.0, bounded), 4)


def verdict_from_score(similarity: float) -> str:
    """Map the composite similarity score to the public risk category."""

    if similarity >= HIGH_RISK_THRESHOLD:
        return "high_risk"
    if similarity >= MEDIUM_RISK_THRESHOLD:
        return "medium_risk"
    return "low_risk"
