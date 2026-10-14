from __future__ import annotations

import logging
import tempfile
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel

from app.config import get_settings
from app.services.firestore_db import (
    delete_clip,
    finalize_clip,
    get_clip,
    get_scan,
    list_clips,
    mark_clip_failed,
    save_pending_clip,
    save_scan_promotion,
)
from app.services.storage import (
    delete_gcs_uri,
    download_gcs_uri,
    move_gcs_uri,
    upload_file,
)
from app.services.style_features import (
    STYLE_EMBEDDING_VERSION,
    StyleFeatureError,
    extract_style_features,
    style_embedding_from_features,
)
from app.services.video import VideoProcessingError, video_duration_seconds
from app.services.video_embeddings import VideoEmbeddingError, embed_video_segments

router = APIRouter()
logger = logging.getLogger(__name__)

ALLOWED_CONTENT_TYPES = {"video/mp4", "video/quicktime"}
ALLOWED_SUFFIXES = {".mp4", ".mov"}


class PromoteScanRequest(BaseModel):
    """Optional metadata used when a checked upload becomes a protected original."""

    title: str = ""
    creator_name: str = ""


def _title_from_filename(filename: str | None) -> str:
    """Turn an uploaded filename into a readable fallback clip title."""

    stem = Path(filename or "clip").stem
    return stem.replace("_", " ").replace("-", " ").strip() or "Untitled clip"


async def _save_upload(upload: UploadFile, target: Path, max_bytes: int) -> int:
    """Stream an uploaded file to disk while enforcing the byte limit."""

    total = 0
    with target.open("wb") as output:
        while chunk := await upload.read(1024 * 1024):
            total += len(chunk)
            if total > max_bytes:
                raise ValueError(f"Video must be smaller than {max_bytes // (1024 * 1024)} MB")
            output.write(chunk)
    return total


def _fingerprint_clip_in_background(
    *,
    clip_id: str,
    temp_path: Path,
    gcs_uri: str,
    duration_seconds: float,
    content_type: str,
    settings,
) -> None:
    """Build both fingerprints and finalize a pending clip after the response."""

    try:
        style_features = extract_style_features(temp_path)
        style_embedding = style_embedding_from_features(style_features)
        embedding_segments = embed_video_segments(
            gcs_uri,
            duration_seconds=duration_seconds,
            mime_type=content_type,
        )
        if not embedding_segments:
            raise VideoEmbeddingError("No video embedding segments were generated")
        finalize_clip(
            clip_id=clip_id,
            embedding_segments=embedding_segments,
            embedding_version=settings.video_embedding_version,
            embedding_model=settings.gemini_video_embedding_model,
            embedding_dimension=len(embedding_segments[0]["embedding"]),
            style_embedding=style_embedding,
            style_embedding_version=STYLE_EMBEDDING_VERSION,
            style_embedding_dimension=len(style_embedding),
        )
        logger.info("Finished fingerprinting clip %s", clip_id)
    except Exception as exc:
        logger.exception("Failed to fingerprint clip %s in the background", clip_id)
        try:
            mark_clip_failed(clip_id, str(exc) or type(exc).__name__)
        except Exception:
            logger.exception("Could not mark clip %s as failed", clip_id)
    finally:
        temp_path.unlink(missing_ok=True)


@router.post("/api/clips/register", status_code=status.HTTP_200_OK)
async def register_clip(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    title: str | None = Form(default=None),
    creator_name: str | None = Form(default=None),
):
    """Upload an original synchronously and fingerprint it in the background."""

    try:
        settings = get_settings()
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    filename = file.filename or "clip.mp4"
    suffix = Path(filename).suffix.lower()
    if file.content_type not in ALLOWED_CONTENT_TYPES and suffix not in ALLOWED_SUFFIXES:
        raise HTTPException(status_code=400, detail="Only MP4 and MOV videos are supported")

    clip_id = f"clip_{uuid4().hex[:12]}"
    gcs_uri = ""
    background_started = False
    temp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            prefix=f"{clip_id}_",
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
        destination = f"originals/{clip_id}{suffix if suffix in ALLOWED_SUFFIXES else '.mp4'}"
        content_type = file.content_type or (
            "video/quicktime" if suffix == ".mov" else "video/mp4"
        )
        gcs_uri = upload_file(
            temp_path,
            destination,
            content_type,
        )
        clip_title = (title or "").strip() or _title_from_filename(filename)
        created_at = save_pending_clip(
            clip_id=clip_id,
            title=clip_title,
            creator_name=(creator_name or "").strip(),
            gcs_uri=gcs_uri,
            content_type=content_type,
            duration_seconds=duration_seconds,
        )
        background_tasks.add_task(
            _fingerprint_clip_in_background,
            clip_id=clip_id,
            temp_path=temp_path,
            gcs_uri=gcs_uri,
            duration_seconds=duration_seconds,
            content_type=content_type,
            settings=settings,
        )
        background_started = True
        return {
            "clip_id": clip_id,
            "title": clip_title,
            "gcs_uri": gcs_uri,
            "status": "processing",
            "message": "Video uploaded. Content and style fingerprinting is running in the background.",
            "created_at": created_at.isoformat(),
        }
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except (VideoProcessingError, VideoEmbeddingError, StyleFeatureError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Failed to register clip %s", clip_id)
        raise HTTPException(status_code=502, detail="Could not register the video") from exc
    finally:
        if gcs_uri and not background_started:
            # Firestore failures should not leave an orphaned original behind.
            try:
                delete_gcs_uri(gcs_uri)
            except Exception:
                logger.warning("Could not clean up %s", gcs_uri, exc_info=True)
        if temp_path is not None and not background_started:
            temp_path.unlink(missing_ok=True)


@router.get("/api/clips")
def get_clips():
    """List protected clips for the catalog screen."""

    return {"clips": list_clips()}


@router.get("/api/clips/{clip_id}")
def get_clip_by_id(clip_id: str):
    """Return one protected clip or a 404 response when it is missing."""

    clip = get_clip(clip_id)
    if clip is None:
        raise HTTPException(status_code=404, detail="Clip not found")
    return clip


@router.post("/api/scans/{scan_id}/move-to-original", status_code=status.HTTP_200_OK)
def move_scan_to_original(
    scan_id: str,
    request: PromoteScanRequest,
    background_tasks: BackgroundTasks,
):
    """Move a checked upload into the protected catalog and fingerprint it in the background."""

    scan = get_scan(scan_id)
    if scan is None:
        raise HTTPException(status_code=404, detail="Scan not found")

    existing_clip_id = scan.get("promoted_clip_id") or ""
    if existing_clip_id:
        existing_clip = get_clip(existing_clip_id) or {}
        return {
            "scan_id": scan_id,
            "clip_id": existing_clip_id,
            "title": existing_clip.get("title") or scan.get("promoted_title") or "",
            "status": existing_clip.get("status") or "processing",
            "already_promoted": True,
        }

    if (scan.get("verdict") or "low_risk") != "low_risk":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only low-risk checked videos can be moved to Originals",
        )

    source_uri = scan.get("suspicious_gcs_uri") or ""
    if not source_uri.startswith("gs://"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This scan has no stored video to move",
        )

    filename = scan.get("source_filename") or "suspicious.mp4"
    suffix = Path(filename).suffix.lower()
    if suffix not in ALLOWED_SUFFIXES:
        suffix = ".mp4"
    clip_id = f"clip_{uuid4().hex[:12]}"
    title = (request.title or "").strip() or _title_from_filename(filename)
    content_type = scan.get("content_type") or (
        "video/quicktime" if suffix == ".mov" else "video/mp4"
    )
    destination = f"originals/{clip_id}{suffix}"
    original_uri = ""
    temp_path: Path | None = None
    background_started = False
    try:
        original_uri = move_gcs_uri(source_uri, destination)
        with tempfile.NamedTemporaryFile(
            prefix=f"{clip_id}_",
            suffix=suffix,
            delete=False,
        ) as temp_file:
            temp_path = Path(temp_file.name)
        download_gcs_uri(original_uri, temp_path)
        duration_seconds = float(scan.get("suspicious_duration_seconds") or 0.0)
        if duration_seconds <= 0:
            raise ValueError("The scan has no valid video duration")
        created_at = save_pending_clip(
            clip_id=clip_id,
            title=title,
            creator_name=(request.creator_name or "").strip(),
            gcs_uri=original_uri,
            content_type=content_type,
            duration_seconds=duration_seconds,
        )
        promoted_at = save_scan_promotion(
            scan_id,
            clip_id=clip_id,
            title=title,
            original_gcs_uri=original_uri,
        )
        settings = get_settings()
        background_tasks.add_task(
            _fingerprint_clip_in_background,
            clip_id=clip_id,
            temp_path=temp_path,
            gcs_uri=original_uri,
            duration_seconds=duration_seconds,
            content_type=content_type,
            settings=settings,
        )
        background_started = True
        return {
            "scan_id": scan_id,
            "clip_id": clip_id,
            "title": title,
            "status": "processing",
            "already_promoted": False,
            "created_at": created_at.isoformat(),
            "promoted_at": promoted_at.isoformat(),
            "message": "Moved to originals. Content and style fingerprinting is running in the background.",
        }
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Failed to move scan %s to originals", scan_id)
        raise HTTPException(status_code=502, detail="Could not move that video to originals") from exc
    finally:
        if temp_path is not None and not background_started:
            temp_path.unlink(missing_ok=True)
        if original_uri and not background_started:
            try:
                # Restore the source path when promotion setup failed after the move.
                move_gcs_uri(original_uri, source_uri.removeprefix("gs://").split("/", 1)[1])
            except Exception:
                logger.warning("Could not restore moved video %s", original_uri, exc_info=True)


@router.delete("/api/clips/{clip_id}")
def remove_clip(clip_id: str):
    """Delete one protected clip and its stored original from the catalog."""

    try:
        deleted = delete_clip(clip_id)
    except Exception as exc:
        logger.exception("Failed to delete clip %s", clip_id)
        raise HTTPException(status_code=502, detail="Could not delete that original") from exc
    if not deleted:
        raise HTTPException(status_code=404, detail="Clip not found")
    return {"deleted": clip_id}
