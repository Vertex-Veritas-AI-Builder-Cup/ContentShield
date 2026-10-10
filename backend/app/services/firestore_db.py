"""Clip metadata helpers.

Teammate 2 can replace the Firestore queries. Function names stay the same:
list_clips() and get_clip(clip_id).
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

from app.config import get_settings

load_dotenv(Path(__file__).resolve().parents[2] / ".env")


def list_clips() -> list[dict]:
    try:
        from google.cloud import firestore

        db = firestore.Client(project=os.getenv("GCP_PROJECT_ID"))
        docs = db.collection("clips").order_by("created_at", direction="DESCENDING").stream()
        clips = []
        for doc in docs:
            data = doc.to_dict() or {}
            clips.append(
                {
                    "clip_id": doc.id,
                    "title": data.get("title") or "",
                    "status": data.get("status") or "unknown",
                    "created_at": str(data.get("created_at") or ""),
                }
            )
        return clips
    except Exception:
        return []


def save_clip(
    *,
    clip_id: str,
    title: str,
    creator_name: str,
    gcs_uri: str,
    embedding_segments: list[dict],
    embedding_version: str,
    embedding_model: str,
    embedding_dimension: int,
    duration_seconds: float,
    keyframe_count: int = 0,
) -> datetime:
    """Persist a registered clip and its versioned video fingerprints."""

    if not embedding_segments:
        raise ValueError("At least one video embedding segment is required")
    if embedding_dimension <= 0:
        raise ValueError("Embedding dimension must be greater than zero")

    from google.cloud import firestore

    created_at = datetime.now(timezone.utc)
    db = firestore.Client(project=os.getenv("GCP_PROJECT_ID"))
    db.collection("clips").document(clip_id).set(
        {
            "title": title,
            "creator_name": creator_name,
            "gcs_uri": gcs_uri,
            "status": "fingerprinted",
            "embedding_version": embedding_version,
            "embedding_model": embedding_model,
            "embedding_dimension": embedding_dimension,
            "embedding_segments": embedding_segments,
            "segment_count": len(embedding_segments),
            "duration_seconds": duration_seconds,
            "keyframe_count": keyframe_count,
            "created_at": created_at,
        }
    )
    return created_at


def list_clip_segment_embeddings() -> list[dict]:
    """Return flattened segment vectors for the current video-embedding path.

    Records from older embedding paths are intentionally ignored. A record that
    claims to use the current path but contains malformed vectors is rejected so
    the index cannot be built from silently corrupted data.
    """

    from google.cloud import firestore

    settings = get_settings()
    db = firestore.Client(project=settings.gcp_project_id)
    records: list[dict] = []
    expected_dimension: int | None = None

    for doc in db.collection("clips").stream():
        data = doc.to_dict() or {}
        if (
            data.get("embedding_version") != settings.video_embedding_version
            or data.get("embedding_model") != settings.gemini_video_embedding_model
        ):
            continue

        try:
            dimension = int(data.get("embedding_dimension") or 0)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Clip {doc.id} has an invalid embedding dimension") from exc
        if dimension <= 0:
            raise ValueError(f"Clip {doc.id} has an invalid embedding dimension")
        if expected_dimension is None:
            expected_dimension = dimension
        elif dimension != expected_dimension:
            raise ValueError("Protected clip embedding dimensions do not match")

        segments = data.get("embedding_segments") or []
        if not segments:
            raise ValueError(f"Clip {doc.id} has no video embedding segments")
        for segment in segments:
            vector = segment.get("embedding") if isinstance(segment, dict) else None
            if not isinstance(vector, list) or len(vector) != dimension:
                raise ValueError(f"Clip {doc.id} has an invalid segment vector")
            records.append(
                {
                    "clip_id": doc.id,
                    "title": data.get("title") or "",
                    "segment_id": segment.get("segment_id") or "",
                    "start_offset_seconds": float(segment.get("start_offset_seconds", 0.0)),
                    "end_offset_seconds": float(segment.get("end_offset_seconds", 0.0)),
                    "embedding": [float(value) for value in vector],
                    "embedding_version": settings.video_embedding_version,
                    "embedding_model": settings.gemini_video_embedding_model,
                    "embedding_dimension": dimension,
                }
            )
    return records


def get_clip(clip_id: str) -> dict | None:
    try:
        from google.cloud import firestore

        db = firestore.Client(project=os.getenv("GCP_PROJECT_ID"))
        doc = db.collection("clips").document(clip_id).get()
        if not doc.exists:
            return None
        data = doc.to_dict() or {}
        return {
            "clip_id": doc.id,
            "title": data.get("title") or "",
            "status": data.get("status") or "unknown",
            "created_at": str(data.get("created_at") or ""),
            "gcs_uri": data.get("gcs_uri") or "",
            "creator_name": data.get("creator_name") or "",
        }
    except Exception:
        return None


def delete_clip(clip_id: str) -> bool:
    """Remove one original: stored file, search entry, then the shelf record.

    Any clip id on the shelf can be deleted. A missing file still clears the record
    so the same person can upload a replacement.
    """

    from google.cloud import firestore

    db = firestore.Client(project=os.getenv("GCP_PROJECT_ID"))
    doc_ref = db.collection("clips").document(clip_id)
    snapshot = doc_ref.get()
    if not snapshot.exists:
        return False

    data = snapshot.to_dict() or {}
    gcs_uri = data.get("gcs_uri") or ""
    if str(gcs_uri).startswith("gs://"):
        _delete_stored_video(str(gcs_uri))
    _remove_from_search_index(clip_id)
    doc_ref.delete()
    return True


def _delete_stored_video(gcs_uri: str) -> None:
    from google.api_core.exceptions import NotFound

    from app.services.storage import delete_gcs_uri

    try:
        delete_gcs_uri(gcs_uri)
    except NotFound:
        return


def _remove_from_search_index(clip_id: str) -> None:
    """Day 3 index lives in faiss_index.remove_clip. Skip until that file exists."""

    try:
        from app.services.faiss_index import remove_clip
    except ImportError:
        return
    remove_clip(clip_id)


def list_scans() -> list[dict]:
    try:
        from google.cloud import firestore

        db = firestore.Client(project=os.getenv("GCP_PROJECT_ID"))
        docs = (
            db.collection("scans")
            .order_by("scanned_at", direction="DESCENDING")
            .limit(50)
            .stream()
        )
        scans = []
        for doc in docs:
            data = doc.to_dict() or {}
            top = data.get("top_match") or {}
            similarity = data.get("top_similarity")
            if similarity is None:
                similarity = top.get("content_similarity") or 0
            verdict = data.get("verdict") or top.get("verdict") or "low_risk"
            scans.append(
                {
                    "scan_id": doc.id,
                    "top_similarity": similarity,
                    "verdict": verdict,
                    "scanned_at": _as_iso(data.get("scanned_at")),
                }
            )
        return scans
    except Exception:
        return []


def save_scan(
    *,
    scan_id: str,
    suspicious_clip_id: str,
    matches: list[dict],
    top_match: dict | None,
    processing_ms: int,
) -> datetime:
    """Persist one backend scan result and return its timestamp."""

    from google.cloud import firestore

    scanned_at = datetime.now(timezone.utc)
    db = firestore.Client(project=get_settings().gcp_project_id)
    top_similarity = float((top_match or {}).get("content_similarity") or 0.0)
    verdict = (top_match or {}).get("verdict") or "low_risk"
    db.collection("scans").document(scan_id).set(
        {
            "suspicious_clip_id": suspicious_clip_id,
            "matches": matches,
            "top_match": top_match,
            "top_similarity": top_similarity,
            "verdict": verdict,
            "processing_ms": int(processing_ms),
            "scanned_at": scanned_at,
        }
    )
    return scanned_at


def _as_iso(value: object) -> str:
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value or "")
