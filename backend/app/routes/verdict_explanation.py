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
    save_verdict_explanation,
)
from app.services.storage import signed_url_for_gcs_uri
from app.services.verdict_explanation import (
    GeminiProviderError,
    VerdictExplanationError,
    explain_top_match,
)


router = APIRouter()


class DmcaRequest(BaseModel):
    """Optional creator and platform fields used to personalize a draft."""

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


def _detail_response(scan: dict[str, Any]) -> dict[str, Any]:
    """Build a frontend-safe detail response without returning embedding vectors."""

    top_match = scan.get("top_match") or {}
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
    if top_match.get("protected_clip_id"):
        protected_clip = get_clip(top_match["protected_clip_id"])
        if protected_clip:
            protected_video_url = signed_url_for_gcs_uri(protected_clip.get("gcs_uri", ""))

    # The browser receives a temporary media URL, never the private gs:// URI.
    safe_protected_clip = None
    if protected_clip:
        safe_protected_clip = {
            key: value for key, value in protected_clip.items() if key != "gcs_uri"
        }

    return {
        **{
            key: value
            for key, value in scan.items()
            if key not in {"suspicious_gcs_uri", "matches", "top_match"}
        },
        "matches": safe_matches,
        "top_match": safe_top_match or None,
        "protected_clip": safe_protected_clip,
        "media": {
            "protected_video_url": protected_video_url,
            "suspicious_video_url": signed_url_for_gcs_uri(scan.get("suspicious_gcs_uri", "")),
        },
    }


@router.get("/api/scans/{scan_id}")
def get_scan_detail(scan_id: str):
    """Return a complete scan, its top protected clip, and persisted Day 4 results."""

    return _detail_response(_load_scan_or_404(scan_id))


@router.post("/api/scans/{scan_id}/explain-verdict")
def explain_scan_verdict(scan_id: str):
    """Generate and persist a grounded explanation for the scan's top verdict."""

    scan = _load_scan_or_404(scan_id)
    top_match = scan.get("top_match") or {}
    if not top_match:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Scan has no top match to explain",
        )

    protected_clip = get_clip(top_match.get("protected_clip_id", ""))
    if not protected_clip:
        raise HTTPException(status_code=422, detail="Protected clip for this scan no longer exists")
    try:
        explanation = explain_top_match(
            suspicious_gcs_uri=scan.get("suspicious_gcs_uri", ""),
            protected_gcs_uri=protected_clip.get("gcs_uri", ""),
            suspicious_mime_type=scan.get("content_type") or "video/mp4",
            protected_title=protected_clip.get("title", ""),
            creator_name=protected_clip.get("creator_name", ""),
            top_match=top_match,
            suspicious_duration_seconds=scan.get("suspicious_duration_seconds") or None,
            protected_duration_seconds=protected_clip.get("duration_seconds") or None,
        )
        save_verdict_explanation(scan_id, explanation)
    except GeminiProviderError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except VerdictExplanationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"scan_id": scan_id, "verdict_explanation": explanation}


@router.post("/api/scans/{scan_id}/dmca")
def create_dmca_draft(scan_id: str, request: DmcaRequest):
    """Create and persist a factual draft notice from stored scan evidence."""

    scan = _load_scan_or_404(scan_id)
    verdict_explanation = scan.get("verdict_explanation") or {}
    try:
        draft = generate_dmca_draft(
            scan=scan,
            verdict_explanation=verdict_explanation,
            creator_name=request.creator_name,
            creator_email=request.creator_email,
            platform=request.platform,
            original_url=request.original_url,
            infringing_url=request.infringing_url,
        )
        save_dmca_draft(scan_id, draft)
    except DmcaDraftError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return {"scan_id": scan_id, "dmca_draft": draft}
