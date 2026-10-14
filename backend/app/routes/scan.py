from __future__ import annotations

import asyncio
import logging
import tempfile
import time
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, File, HTTPException, UploadFile, status

from app.config import get_settings
from app.services.faiss_index import (
    SearchIndexError,
    build_segment_index,
    search_video_segments,
)
from app.services.firestore_db import list_scans, save_scan
from app.services.storage import delete_gcs_uri, upload_file
from app.services.video import VideoProcessingError, video_duration_seconds
from app.services.video_embeddings import VideoEmbeddingError, embed_video_segments


router = APIRouter()
logger = logging.getLogger(__name__)

ALLOWED_CONTENT_TYPES = {"video/mp4", "video/quicktime"}
ALLOWED_SUFFIXES = {".mp4", ".mov"}


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


def _evaluate_content(
    suspicious_uri: str,
    *,
    duration_seconds: float,
    content_type: str,
) -> tuple[list[dict], dict | None]:
    """Embed and search content in one worker thread."""

    query_segments = embed_video_segments(
        suspicious_uri,
        duration_seconds=duration_seconds,
        mime_type=content_type,
    )
    matches = search_video_segments(query_segments)
    return matches, matches[0] if matches else None


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
        matches, top_match = await asyncio.to_thread(
            _evaluate_content,
            suspicious_uri,
            duration_seconds=duration_seconds,
            content_type=content_type,
        )
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
        )
        persisted = True
        return {
            "scan_id": scan_id,
            "suspicious_clip_id": suspicious_clip_id,
            "scanned_at": scanned_at.isoformat(),
            "matches": matches,
            "top_match": top_match,
            "processing_ms": processing_ms,
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
