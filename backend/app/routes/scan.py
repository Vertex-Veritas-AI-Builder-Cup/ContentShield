from __future__ import annotations

import logging
import tempfile
import time
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, File, HTTPException, UploadFile, status

from app.config import get_settings
from app.services.faiss_index import (
    SearchIndexError,
    StyleSearchError,
    build_segment_index,
    search_style_embeddings,
    search_video_segments,
)
from app.services.firestore_db import list_scans, save_scan
from app.services.storage import delete_gcs_uri, upload_file
from app.services.style_features import (
    STYLE_MATCH_THRESHOLD,
    StyleFeatureError,
    extract_style_features,
    style_embedding_from_features,
)
from app.services.video import VideoProcessingError, video_duration_seconds
from app.services.video_embeddings import VideoEmbeddingError, embed_video_segments
from app.services.verdict import HIGH_RISK_THRESHOLD


router = APIRouter()
logger = logging.getLogger(__name__)

ALLOWED_CONTENT_TYPES = {"video/mp4", "video/quicktime"}
ALLOWED_SUFFIXES = {".mp4", ".mov"}


def _should_evaluate_style(top_match: dict | None) -> bool:
    """Evaluate style only when content matching did not already find a strong copy."""

    return not top_match or float(top_match.get("content_similarity") or 0.0) < HIGH_RISK_THRESHOLD


async def _save_upload(upload: UploadFile, target: Path, max_bytes: int) -> int:
    """Stream a suspicious upload to a temporary file within the size limit."""

    total = 0
    with target.open("wb") as output:
        while chunk := await upload.read(1024 * 1024):
            total += len(chunk)
            if total > max_bytes:
                raise ValueError(f"Video must be smaller than {max_bytes // (1024 * 1024)} MB")
            output.write(chunk)
    return total


@router.post("/api/scan", status_code=status.HTTP_200_OK)
async def scan_video(file: UploadFile = File(...)):
    """Embed an uploaded suspicious video, search protected clips, and save the scan."""

    started = time.monotonic()
    try:
        settings = get_settings()
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    filename = file.filename or "scan.mp4"
    suffix = Path(filename).suffix.lower()
    if file.content_type not in ALLOWED_CONTENT_TYPES and suffix not in ALLOWED_SUFFIXES:
        raise HTTPException(status_code=400, detail="Only MP4 and MOV videos are supported")

    scan_id = f"scan_{uuid4().hex[:12]}"
    suspicious_clip_id = f"susp_{uuid4().hex[:12]}"
    suspicious_uri = ""
    temp_path: Path | None = None
    persisted = False
    try:
        with tempfile.NamedTemporaryFile(
            prefix=f"{suspicious_clip_id}_",
            suffix=suffix if suffix in ALLOWED_SUFFIXES else ".mp4",
            delete=False,
        ) as temp_file:
            temp_path = Path(temp_file.name)

        await _save_upload(file, temp_path, settings.max_upload_bytes)
        duration_seconds = video_duration_seconds(temp_path)
        if duration_seconds > settings.max_video_seconds:
            raise ValueError(
                f"Video must be {settings.max_video_seconds} seconds or shorter"
            )

        content_type = file.content_type or (
            "video/quicktime" if suffix == ".mov" else "video/mp4"
        )
        destination = f"suspicious/{suspicious_clip_id}{suffix if suffix in ALLOWED_SUFFIXES else '.mp4'}"

        # Build once before uploading so an empty protected catalog does not
        # leave a suspicious object behind.
        build_segment_index()
        suspicious_uri = upload_file(temp_path, destination, content_type)
        query_segments = embed_video_segments(
            suspicious_uri,
            duration_seconds=duration_seconds,
            mime_type=content_type,
        )
        matches = search_video_segments(query_segments)
        top_match = matches[0] if matches else None
        style_evaluated = False
        style_skip_reason: str | None = None
        style_match: dict | None = None
        style_notice: dict | None = None
        if not _should_evaluate_style(top_match):
            style_skip_reason = "strong_content_match"
        else:
            try:
                style_features = extract_style_features(temp_path)
                style_embedding = style_embedding_from_features(style_features)
                style_match = search_style_embeddings(style_embedding)
                style_evaluated = True
                if style_match["style_similarity"] >= STYLE_MATCH_THRESHOLD:
                    title = style_match.get("protected_title") or style_match["protected_clip_id"]
                    style_notice = {
                        "type": "similar_style",
                        "protected_clip_id": style_match["protected_clip_id"],
                        "protected_title": style_match.get("protected_title") or "",
                        "style_similarity": style_match["style_similarity"],
                        "message": f"Similar editing style detected with {title}.",
                        "disclaimer": "Style similarity is not a copyright or legal conclusion.",
                    }
            except StyleSearchError:
                style_skip_reason = "no_compatible_style_embeddings"
            except StyleFeatureError:
                logger.warning("Style analysis unavailable for scan %s", scan_id, exc_info=True)
                style_skip_reason = "style_analysis_unavailable"
        processing_ms = int((time.monotonic() - started) * 1000)
        scanned_at = save_scan(
            scan_id=scan_id,
            suspicious_clip_id=suspicious_clip_id,
            suspicious_gcs_uri=suspicious_uri,
            source_filename=filename,
            content_type=content_type,
            suspicious_duration_seconds=duration_seconds,
            matches=matches,
            top_match=top_match,
            processing_ms=processing_ms,
            style_evaluated=style_evaluated,
            style_skip_reason=style_skip_reason,
            style_match=style_match,
            style_notice=style_notice,
        )
        persisted = True
        return {
            "scan_id": scan_id,
            "suspicious_clip_id": suspicious_clip_id,
            "scanned_at": scanned_at.isoformat(),
            "matches": matches,
            "top_match": top_match,
            "processing_ms": processing_ms,
            "style_evaluated": style_evaluated,
            "style_skip_reason": style_skip_reason,
            "style_match": style_match,
            "style_notice": style_notice,
        }
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except (VideoProcessingError, VideoEmbeddingError, SearchIndexError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Failed to scan video %s", scan_id)
        raise HTTPException(status_code=502, detail="Could not scan the video") from exc
    finally:
        if suspicious_uri and not persisted:
            try:
                delete_gcs_uri(suspicious_uri)
            except Exception:
                logger.warning("Could not clean up %s", suspicious_uri, exc_info=True)
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)


@router.get("/api/scans")
def get_scans():
    """Return persisted scan summaries for the monitor feed."""

    return {"scans": list_scans()}
