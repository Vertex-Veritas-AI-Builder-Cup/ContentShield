from __future__ import annotations

import logging
import tempfile
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status

from app.config import get_settings
from app.services.firestore_db import get_clip
from app.services.storage import download_gcs_uri
from app.services.style_features import StyleFeatureError, compare_style_features, extract_style_features
from app.services.video import video_duration_seconds


router = APIRouter()
logger = logging.getLogger(__name__)
ALLOWED_CONTENT_TYPES = {"video/mp4", "video/quicktime"}
ALLOWED_SUFFIXES = {".mp4", ".mov"}


async def _save_upload(upload: UploadFile, target: Path, max_bytes: int) -> None:
    total = 0
    with target.open("wb") as output:
        while chunk := await upload.read(1024 * 1024):
            total += len(chunk)
            if total > max_bytes:
                raise ValueError(f"Video must be smaller than {max_bytes // (1024 * 1024)} MB")
            output.write(chunk)


@router.post("/api/style-match", status_code=status.HTTP_200_OK)
async def style_match(
    file: UploadFile = File(...),
    protected_clip_id: str = Form(...),
    transcript: str = Form(default=""),
):
    """Compare bounded editing-style signals separately from content matching."""

    try:
        settings = get_settings()
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    filename = file.filename or "style-query.mp4"
    suffix = Path(filename).suffix.lower()
    if file.content_type not in ALLOWED_CONTENT_TYPES and suffix not in ALLOWED_SUFFIXES:
        raise HTTPException(status_code=400, detail="Only MP4 and MOV videos are supported")
    protected_clip = get_clip(protected_clip_id)
    if not protected_clip or not protected_clip.get("gcs_uri", "").startswith("gs://"):
        raise HTTPException(status_code=404, detail="Protected clip not found")

    query_path: Path | None = None
    reference_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(suffix=suffix if suffix in ALLOWED_SUFFIXES else ".mp4", delete=False) as output:
            query_path = Path(output.name)
        await _save_upload(file, query_path, settings.max_upload_bytes)
        if video_duration_seconds(query_path) > settings.max_video_seconds:
            raise ValueError(f"Video must be {settings.max_video_seconds} seconds or shorter")
        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as output:
            reference_path = Path(output.name)
        download_gcs_uri(protected_clip["gcs_uri"], reference_path)
        query_features = extract_style_features(query_path, transcript=transcript)
        reference_features = extract_style_features(reference_path)
        comparison = compare_style_features(query_features, reference_features)
        return {
            "style_match_id": f"style_{uuid4().hex[:12]}",
            "protected_clip_id": protected_clip_id,
            "style_feature_version": query_features["style_feature_version"],
            "query_features": query_features,
            "protected_features": reference_features,
            "comparison": comparison,
        }
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except StyleFeatureError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Failed to compare style for protected clip %s", protected_clip_id)
        raise HTTPException(status_code=502, detail="Could not compare video style") from exc
    finally:
        if query_path is not None:
            query_path.unlink(missing_ok=True)
        if reference_path is not None:
            reference_path.unlink(missing_ok=True)
