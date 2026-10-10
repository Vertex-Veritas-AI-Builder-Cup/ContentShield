from __future__ import annotations

import logging
import tempfile
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status

from app.config import get_settings
from app.services.embeddings import EmbeddingError, embed_video
from app.services.firestore_db import delete_clip, get_clip, list_clips, save_clip
from app.services.storage import delete_gcs_uri, upload_file
from app.services.video import VideoProcessingError, extract_keyframes, video_duration_seconds

router = APIRouter()
logger = logging.getLogger(__name__)

ALLOWED_CONTENT_TYPES = {"video/mp4", "video/quicktime"}
ALLOWED_SUFFIXES = {".mp4", ".mov"}


def _title_from_filename(filename: str | None) -> str:
    stem = Path(filename or "clip").stem
    return stem.replace("_", " ").replace("-", " ").strip() or "Untitled clip"


async def _save_upload(upload: UploadFile, target: Path, max_bytes: int) -> int:
    total = 0
    with target.open("wb") as output:
        while chunk := await upload.read(1024 * 1024):
            total += len(chunk)
            if total > max_bytes:
                raise ValueError(f"Video must be smaller than {max_bytes // (1024 * 1024)} MB")
            output.write(chunk)
    return total


@router.post("/api/clips/register", status_code=status.HTTP_201_CREATED)
async def register_clip(
    file: UploadFile = File(...),
    title: str | None = Form(default=None),
    creator_name: str | None = Form(default=None),
):
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
    persisted = False
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

        with tempfile.TemporaryDirectory(prefix=f"{clip_id}_frames_") as frame_dir:
            frames = extract_keyframes(temp_path, Path(frame_dir), count=8)
            logger.info(f"Extracted {len(frames)} keyframes from {temp_path}")
            embedding = embed_video(frames, duration_seconds)

        destination = f"originals/{clip_id}{suffix if suffix in ALLOWED_SUFFIXES else '.mp4'}"
        gcs_uri = upload_file(
            temp_path,
            destination,
            file.content_type or "video/mp4",
        )
        created_at = save_clip(
            clip_id=clip_id,
            title=(title or "").strip() or _title_from_filename(filename),
            creator_name=(creator_name or "").strip(),
            gcs_uri=gcs_uri,
            embedding=embedding,
            duration_seconds=duration_seconds,
            keyframe_count=len(frames),
        )
        persisted = True
        return {
            "clip_id": clip_id,
            "title": (title or "").strip() or _title_from_filename(filename),
            "gcs_uri": gcs_uri,
            "status": "fingerprinted",
            "embedding_dimensions": len(embedding),
            "created_at": created_at.isoformat(),
        }
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except (VideoProcessingError, EmbeddingError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Failed to register clip %s", clip_id)
        raise HTTPException(status_code=502, detail="Could not register the video") from exc
    finally:
        if gcs_uri and not persisted:
            # Firestore failures should not leave an orphaned original behind.
            try:
                delete_gcs_uri(gcs_uri)
            except Exception:
                logger.warning("Could not clean up %s", gcs_uri, exc_info=True)
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)


@router.get("/api/clips")
def get_clips():
    return {"clips": list_clips()}


@router.get("/api/clips/{clip_id}")
def get_clip_by_id(clip_id: str):
    clip = get_clip(clip_id)
    if clip is None:
        raise HTTPException(status_code=404, detail="Clip not found")
    return clip


@router.delete("/api/clips/{clip_id}")
def remove_clip(clip_id: str):
    if not delete_clip(clip_id):
        raise HTTPException(status_code=404, detail="Clip not found")
    return {"deleted": clip_id}
