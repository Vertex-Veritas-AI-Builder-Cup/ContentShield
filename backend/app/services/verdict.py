"""Content-match risk labels. Scan uses this so the thresholds stay in one place."""

HIGH_RISK_THRESHOLD = 0.75


def verdict_from_score(similarity: float) -> str:
    """Map a cosine-similarity score to the public risk category."""

    if similarity >= HIGH_RISK_THRESHOLD:
        return "high_risk"
    if similarity >= 0.50:
        return "medium_risk"
    return "low_risk"
