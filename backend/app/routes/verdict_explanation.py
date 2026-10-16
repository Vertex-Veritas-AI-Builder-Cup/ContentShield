"""Routes for explaining scan matches and preparing reviewable notice drafts."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from app.services.dmca import DmcaDraftError, generate_dmca_draft
from app.services.firestore_db import (
    get_clip,
    get_scan,
    save_dmca_draft,
    save_match_dmca_draft,
    save_match_verdict_explanation,
    save_verdict_explanation,
)
from app.services.storage import signed_url_for_gcs_uri
from app.services.verdict_explanation import (
    GeminiProviderError,
    VerdictExplanationError,
    explain_top_match,
)


router = APIRouter()


class MatchSelectionRequest(BaseModel):
    """Identify which protected original a review action should use."""

    protected_clip_id: str = ""


class DmcaRequest(BaseModel):
    """Optional creator and platform fields used to personalize a draft."""

    protected_clip_id: str = ""
    creator_name: str = ""
    creator_email: str = ""
    platform: str = ""
    original_url: str = ""
    infringing_url: str = ""


def _load_scan_or_404(scan_id: str) -> dict[str, Any]:
    """Load a scan or translate an unknown ID into a consistent API 404."""

    scan = get_scan(scan_id)
    if scan is None:
        raise HTTPException(status_code=404, detail="Scan not found")
    return scan


def _select_match(scan: dict[str, Any], protected_clip_id: str | None = None) -> dict[str, Any] | None:
    """Return a requested match after confirming it belongs to this scan."""

    top_match = scan.get("top_match") or {}
    requested_id = (protected_clip_id or "").strip()
    if not requested_id:
        return top_match or None
    if requested_id == top_match.get("protected_clip_id"):
        return top_match
    for match in scan.get("matches") or []:
        if isinstance(match, dict) and match.get("protected_clip_id") == requested_id:
            return match
    raise HTTPException(status_code=404, detail="That match is not part of this scan")


def _review_for_match(scan: dict[str, Any], protected_clip_id: str) -> dict[str, Any]:
    """Read the selected match's persisted explanation and draft, if available."""

    reviews = scan.get("match_reviews") or {}
    review = reviews.get(protected_clip_id) if isinstance(reviews, dict) else None
    return review if isinstance(review, dict) else {}


def _detail_response(
    scan: dict[str, Any], protected_clip_id: str | None = None
) -> dict[str, Any]:
    """Build a frontend-safe detail response without returning embedding vectors."""

    top_match = scan.get("top_match") or {}
    selected_match = _select_match(scan, protected_clip_id)
    selected_match_id = (selected_match or {}).get("protected_clip_id")
    safe_matches = [
        {
            key: value
            for key, value in match.items()
            if key not in {"embedding", "gcs_uri", "protected_gcs_uri"}
        }
        for match in scan.get("matches") or []
        if isinstance(match, dict)
    ]
    safe_top_match = {
        key: value
        for key, value in top_match.items()
        if key not in {"embedding", "gcs_uri", "protected_gcs_uri"}
    }
    protected_clip = None
    protected_video_url = None
    if selected_match_id:
        protected_clip = get_clip(selected_match_id)
        if protected_clip:
            protected_video_url = signed_url_for_gcs_uri(protected_clip.get("gcs_uri", ""))

    # The browser receives a temporary media URL, never the private gs:// URI.
    safe_protected_clip = None
    if protected_clip:
        safe_protected_clip = {
            key: value for key, value in protected_clip.items() if key != "gcs_uri"
        }

    selected_review = _review_for_match(scan, selected_match_id) if selected_match_id else {}
    selected_explanation = selected_review.get("verdict_explanation")
    selected_draft = selected_review.get("dmca_draft")
    if selected_match_id == top_match.get("protected_clip_id"):
        selected_explanation = selected_explanation or scan.get("verdict_explanation")
        selected_draft = selected_draft or scan.get("dmca_draft")

    safe_selected_match = {
        key: value
        for key, value in (selected_match or {}).items()
        if key not in {"embedding", "gcs_uri", "protected_gcs_uri"}
    }

    return {
        **{
            key: value
            for key, value in scan.items()
            if key not in {"suspicious_gcs_uri", "matches", "top_match", "match_reviews"}
        },
        "matches": safe_matches,
        "top_match": safe_top_match or None,
        "selected_match": safe_selected_match or None,
        "selected_match_id": selected_match_id,
        "selected_verdict_explanation": selected_explanation,
        "selected_dmca_draft": selected_draft,
        "protected_clip": safe_protected_clip,
        "media": {
            "protected_video_url": protected_video_url,
            "suspicious_video_url": signed_url_for_gcs_uri(scan.get("suspicious_gcs_uri", "")),
        },
    }


@router.get("/api/scans/{scan_id}")
def get_scan_detail(scan_id: str, match_id: str | None = None):
    """Return a complete scan, optionally focused on one protected match."""

    return _detail_response(_load_scan_or_404(scan_id), match_id)


@router.post("/api/scans/{scan_id}/explain-verdict")
def explain_scan_verdict(scan_id: str, request: MatchSelectionRequest | None = None):
    """Generate and persist a grounded explanation for one selected match."""

    scan = _load_scan_or_404(scan_id)
    protected_clip_id = (request.protected_clip_id if request else "").strip()
    selected_match = _select_match(scan, protected_clip_id)
    if not selected_match:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Scan has no match to explain",
        )

    selected_id = selected_match.get("protected_clip_id", "")
    existing_review = _review_for_match(scan, selected_id)
    existing_explanation = existing_review.get("verdict_explanation")
    if selected_id == (scan.get("top_match") or {}).get("protected_clip_id"):
        existing_explanation = existing_explanation or scan.get("verdict_explanation")
    if existing_explanation:
        return {"scan_id": scan_id, "protected_clip_id": selected_id, "verdict_explanation": existing_explanation}

    protected_clip = get_clip(selected_id)
    if not protected_clip:
        raise HTTPException(status_code=422, detail="Protected clip for this scan no longer exists")
    try:
        explanation = explain_top_match(
            suspicious_gcs_uri=scan.get("suspicious_gcs_uri", ""),
            protected_gcs_uri=protected_clip.get("gcs_uri", ""),
            suspicious_mime_type=scan.get("content_type") or "video/mp4",
            protected_title=protected_clip.get("title", ""),
            creator_name=protected_clip.get("creator_name", ""),
            top_match=selected_match,
            suspicious_duration_seconds=scan.get("suspicious_duration_seconds") or None,
            protected_duration_seconds=protected_clip.get("duration_seconds") or None,
        )
        if selected_id == (scan.get("top_match") or {}).get("protected_clip_id"):
            save_verdict_explanation(scan_id, explanation)
        else:
            save_match_verdict_explanation(scan_id, selected_id, explanation)
    except GeminiProviderError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except VerdictExplanationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {
        "scan_id": scan_id,
        "protected_clip_id": selected_id,
        "verdict_explanation": explanation,
    }


@router.post("/api/scans/{scan_id}/dmca")
def create_dmca_draft(scan_id: str, request: DmcaRequest):
    """Create and persist a factual draft notice from stored scan evidence."""

    scan = _load_scan_or_404(scan_id)
    selected_match = _select_match(scan, request.protected_clip_id)
    if not selected_match:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Scan has no match for a draft")
    selected_id = selected_match.get("protected_clip_id", "")
    review = _review_for_match(scan, selected_id)
    verdict_explanation = review.get("verdict_explanation")
    if selected_id == (scan.get("top_match") or {}).get("protected_clip_id"):
        verdict_explanation = verdict_explanation or scan.get("verdict_explanation")
    protected_clip = get_clip(selected_id)
    if not protected_clip:
        raise HTTPException(status_code=422, detail="Protected clip for this scan no longer exists")
    protected_media_url = signed_url_for_gcs_uri(
        protected_clip.get("gcs_uri", "")
    )
    suspicious_media_url = signed_url_for_gcs_uri(scan.get("suspicious_gcs_uri", ""))
    try:
        draft = generate_dmca_draft(
            scan=scan,
            verdict_explanation=verdict_explanation or {},
            match=selected_match,
            creator_name=request.creator_name,
            creator_email=request.creator_email,
            platform=request.platform,
            original_url=request.original_url,
            infringing_url=request.infringing_url,
            protected_media_url=protected_media_url or "",
            suspicious_media_url=suspicious_media_url or "",
        )
        if selected_id == (scan.get("top_match") or {}).get("protected_clip_id"):
            save_dmca_draft(scan_id, draft)
        else:
            save_match_dmca_draft(scan_id, selected_id, draft)
    except DmcaDraftError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return {"scan_id": scan_id, "protected_clip_id": selected_id, "dmca_draft": draft}
