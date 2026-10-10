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
    clip = get_clip(clip_id)
    if clip is None:
        return False

    gcs_uri = clip.get("gcs_uri") or ""
    if gcs_uri.startswith("gs://"):
        _delete_gcs_object(gcs_uri)

    from google.cloud import firestore

    db = firestore.Client(project=os.getenv("GCP_PROJECT_ID"))
    db.collection("clips").document(clip_id).delete()
    return True


def _delete_gcs_object(gcs_uri: str) -> None:
    """Remove the video file. Teammate 2 can move this into services/storage.py."""
    rest = gcs_uri.removeprefix("gs://")
    bucket_name, _, blob_name = rest.partition("/")
    if not bucket_name or not blob_name:
        return
    from google.cloud import storage

    client = storage.Client(project=os.getenv("GCP_PROJECT_ID"))
    client.bucket(bucket_name).blob(blob_name).delete()
