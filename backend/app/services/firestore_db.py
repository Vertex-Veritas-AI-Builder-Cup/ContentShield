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
    """Return the public catalog fields for protected clips, newest first."""

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
    content_type: str = "video/mp4",
    keyframe_count: int = 0,
    style_embedding: list[float] | None = None,
    style_embedding_version: str = "",
    style_embedding_dimension: int = 0,
) -> datetime:
    """Persist a registered clip and its content/style fingerprints."""

    if not embedding_segments:
        raise ValueError("At least one video embedding segment is required")
    if embedding_dimension <= 0:
        raise ValueError("Embedding dimension must be greater than zero")

    from google.cloud import firestore

    created_at = datetime.now(timezone.utc)
    db = firestore.Client(project=os.getenv("GCP_PROJECT_ID"))
    clip_data = {
            "title": title,
            "creator_name": creator_name,
            "gcs_uri": gcs_uri,
            "content_type": content_type,
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
    if style_embedding is not None:
        if not style_embedding_version or style_embedding_dimension <= 0:
            raise ValueError("Style embedding metadata is required")
        if len(style_embedding) != style_embedding_dimension:
            raise ValueError("Style embedding dimension does not match its vector")
        clip_data.update(
            {
                "style_embedding": style_embedding,
                "style_embedding_version": style_embedding_version,
                "style_embedding_dimension": style_embedding_dimension,
            }
        )
    db.collection("clips").document(clip_id).set(clip_data)
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


def list_clip_style_embeddings() -> list[dict]:
    """Return clip-level style vectors compatible with the current style path."""

    from app.services.style_features import STYLE_EMBEDDING_DIMENSION, STYLE_EMBEDDING_VERSION
    from google.cloud import firestore

    db = firestore.Client(project=get_settings().gcp_project_id)
    records: list[dict] = []
    for doc in db.collection("clips").stream():
        data = doc.to_dict() or {}
        if (
            data.get("style_embedding_version") != STYLE_EMBEDDING_VERSION
            or int(data.get("style_embedding_dimension") or 0) != STYLE_EMBEDDING_DIMENSION
        ):
            continue
        vector = data.get("style_embedding")
        if not isinstance(vector, list) or len(vector) != STYLE_EMBEDDING_DIMENSION:
            raise ValueError(f"Clip {doc.id} has an invalid style embedding")
        records.append(
            {
                "clip_id": doc.id,
                "title": data.get("title") or "",
                "style_embedding": [float(value) for value in vector],
                "style_embedding_version": STYLE_EMBEDDING_VERSION,
                "style_embedding_dimension": STYLE_EMBEDDING_DIMENSION,
            }
        )
    return records


def get_clip(clip_id: str) -> dict | None:
    """Fetch one protected clip's public metadata or return ``None`` if absent."""

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
            "content_type": data.get("content_type") or "",
            "duration_seconds": float(data.get("duration_seconds") or 0.0),
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
    """Delete a stored original while treating an already-missing object as safe."""

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
    """Return the latest persisted scan summaries in the frontend response shape."""

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


def get_scan(scan_id: str) -> dict | None:
    """Fetch one complete scan record without exposing protected embeddings."""

    from google.cloud import firestore

    db = firestore.Client(project=get_settings().gcp_project_id)
    snapshot = db.collection("scans").document(scan_id).get()
    if not snapshot.exists:
        return None

    data = snapshot.to_dict() or {}
    return {
        "scan_id": snapshot.id,
        "suspicious_clip_id": data.get("suspicious_clip_id") or "",
        "suspicious_gcs_uri": data.get("suspicious_gcs_uri") or "",
        "source_filename": data.get("source_filename") or "",
        "content_type": data.get("content_type") or "",
        "suspicious_duration_seconds": float(
            data.get("suspicious_duration_seconds") or 0.0
        ),
        "matches": data.get("matches") or [],
        "top_match": data.get("top_match"),
        "top_similarity": float(data.get("top_similarity") or 0.0),
        "verdict": data.get("verdict") or "low_risk",
        "processing_ms": int(data.get("processing_ms") or 0),
        "scanned_at": _as_iso(data.get("scanned_at")),
        "style_evaluated": bool(data.get("style_evaluated")),
        "style_skip_reason": data.get("style_skip_reason"),
        "style_match": data.get("style_match"),
        "style_notice": data.get("style_notice"),
        "verdict_explanation": data.get("verdict_explanation"),
        "dmca_draft": data.get("dmca_draft"),
    }


def save_scan(
    *,
    scan_id: str,
    suspicious_clip_id: str,
    suspicious_gcs_uri: str = "",
    source_filename: str = "",
    content_type: str = "",
    suspicious_duration_seconds: float = 0.0,
    matches: list[dict],
    top_match: dict | None,
    processing_ms: int,
    style_evaluated: bool = False,
    style_skip_reason: str | None = None,
    style_match: dict | None = None,
    style_notice: dict | None = None,
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
            "suspicious_gcs_uri": suspicious_gcs_uri,
            "source_filename": source_filename,
            "content_type": content_type,
            "suspicious_duration_seconds": float(suspicious_duration_seconds),
            "matches": matches,
            "top_match": top_match,
            "top_similarity": top_similarity,
            "verdict": verdict,
            "processing_ms": int(processing_ms),
            "scanned_at": scanned_at,
            "style_evaluated": style_evaluated,
            "style_skip_reason": style_skip_reason,
            "style_match": style_match,
            "style_notice": style_notice,
        }
    )
    return scanned_at


def save_verdict_explanation(scan_id: str, explanation: dict) -> None:
    """Attach one validated verdict explanation to an existing scan document."""

    from google.cloud import firestore

    db = firestore.Client(project=get_settings().gcp_project_id)
    db.collection("scans").document(scan_id).update(
        {"verdict_explanation": explanation}
    )


def save_dmca_draft(scan_id: str, draft: dict) -> None:
    """Attach one generated DMCA draft to an existing scan document."""

    from google.cloud import firestore

    db = firestore.Client(project=get_settings().gcp_project_id)
    db.collection("scans").document(scan_id).update({"dmca_draft": draft})


def _as_iso(value: object) -> str:
    """Serialize Firestore timestamps and fallback values for JSON responses."""

    if isinstance(value, datetime):
        return value.isoformat()
    return str(value or "")
