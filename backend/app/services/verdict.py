"""Content-match risk labels. Scan uses this so the thresholds stay in one place."""


def verdict_from_score(similarity: float) -> str:
    """Map a cosine-similarity score to the public risk category."""

    if similarity >= 0.75:
        return "high_risk"
    if similarity >= 0.50:
        return "medium_risk"
    return "low_risk"
