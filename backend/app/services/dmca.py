"""Deterministic, reviewable takedown-draft generation."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4


class DmcaDraftError(ValueError):
    """Represent missing evidence or invalid metadata for a draft."""


def _text(value: object, fallback: str = "Not provided") -> str:
    """Normalize optional user or Firestore metadata before template insertion."""

    cleaned = str(value or "").strip()
    return cleaned or fallback


def _url(value: object) -> str:
    """Keep notice URLs compact for the generated draft body."""

    cleaned = str(value or "").strip()
    return cleaned[:15] or "Not provided"


def generate_dmca_draft(
    *,
    scan: dict[str, Any],
    verdict_explanation: dict[str, Any],
    creator_name: str = "",
    creator_email: str = "",
    platform: str = "",
    original_url: str = "",
    infringing_url: str = "",
    protected_media_url: str = "",
    suspicious_media_url: str = "",
) -> dict[str, Any]:
    """Build a factual draft from stored verdict evidence without inventing legal facts."""

    top_match = scan.get("top_match") or {}
    if not top_match:
        raise DmcaDraftError("A scan must have a top match before a draft can be created")
    if not verdict_explanation.get("explanation"):
        raise DmcaDraftError(
            "A verdict explanation is required before a draft can be created"
        )

    title = _text(top_match.get("protected_title"), "Protected original")
    decision = _text(verdict_explanation.get("decision"), "uncertain")
    similarity = float(top_match.get("content_similarity") or 0.0)
    evidence_lines = []
    for item in verdict_explanation.get("evidence") or []:
        evidence_lines.append(
            "- Suspicious {:.1f}s–{:.1f}s / original {:.1f}s–{:.1f}s: {}".format(
                float(item.get("query_start_seconds") or 0),
                float(item.get("query_end_seconds") or 0),
                float(item.get("protected_start_seconds") or 0),
                float(item.get("protected_end_seconds") or 0),
                _text(item.get("observation")),
            )
        )
    if not evidence_lines:
        evidence_lines.append("- No timestamped evidence was returned by the verdict-explanation step.")

    body = f"""Hello,

I am requesting a review of a video that may reproduce protected content.

Protected original: {title}
Creator: {_text(creator_name)}
Platform: {_text(platform)}
Original URL: {_url(original_url)}
Potentially infringing URL: {_url(infringing_url)}

ContentShield evidence links (temporary signed URLs):
- Protected original video: {_url(protected_media_url)}
- Suspicious video: {_url(suspicious_media_url)}

ContentShield assessment:
- Similarity score: {similarity:.3f}
- Verdict-explanation decision: {decision}
- Explanation: {_text(verdict_explanation.get("explanation"))}

Evidence:
{chr(10).join(evidence_lines)}

Limitations:
{chr(10).join(f"- {_text(item)}" for item in verdict_explanation.get("limitations") or ["No additional limitations were recorded."])}

Please review the original files, ownership information, and applicable platform
requirements before submitting this draft.

Regards,
{_text(creator_name)}
{_text(creator_email)}
""".strip()

    return {
        "draft_id": f"dmca_{uuid4().hex[:12]}",
        "subject": f"Copyright concern regarding copied video: {title}",
        "body": body,
        "disclaimer": "Draft for creator and legal review; not legal advice.",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
