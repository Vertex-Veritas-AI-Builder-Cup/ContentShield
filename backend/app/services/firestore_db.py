"""Clip metadata helpers.

Teammate 2 can replace the Firestore queries. Function names stay the same:
list_clips() and get_clip(clip_id).
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

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
    embedding: list[float],
    duration_seconds: float,
    keyframe_count: int,
) -> datetime:
    """Persist a registered clip and its content fingerprint."""

    from google.cloud import firestore

    created_at = datetime.now(timezone.utc)
    db = firestore.Client(project=os.getenv("GCP_PROJECT_ID"))
    db.collection("clips").document(clip_id).set(
        {
            "title": title,
            "creator_name": creator_name,
            "gcs_uri": gcs_uri,
            "status": "fingerprinted",
            "embedding": embedding,
            "embedding_dimensions": len(embedding),
            "duration_seconds": duration_seconds,
            "keyframe_count": keyframe_count,
            "created_at": created_at,
        }
    )
    return created_at


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


def _as_iso(value: object) -> str:
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value or "")
