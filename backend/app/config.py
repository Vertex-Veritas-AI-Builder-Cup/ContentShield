"""Application configuration loaded from ``backend/.env``."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


BACKEND_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(BACKEND_ROOT / ".env")


@dataclass(frozen=True)
class Settings:
    gcp_project_id: str
    gcp_location: str
    gcs_bucket: str
    gemini_analysis_model: str
    gemini_embedding_model: str
    max_upload_bytes: int
    max_video_seconds: int


def get_settings() -> Settings:
    """Return validated settings for the current process.

    Google client libraries also honor ``GOOGLE_APPLICATION_CREDENTIALS``
    themselves. Keeping that variable in the environment lets local runs and
    Cloud Run's attached service account use the same code path.
    """

    project_id = os.getenv("GCP_PROJECT_ID", "").strip()
    bucket = os.getenv("GCS_BUCKET_DEV", "").strip()
    if not project_id:
        raise RuntimeError("GCP_PROJECT_ID is not configured")
    if not bucket:
        raise RuntimeError("GCS_BUCKET_DEV is not configured")

    return Settings(
        gcp_project_id=project_id,
        gcp_location=os.getenv("GCP_LOCATION", "us-central1").strip(),
        gcs_bucket=bucket,
        # The pinned google-genai SDK exposes text embeddings. We create a
        # multimodal summary from keyframes first, then embed that summary.
        gemini_analysis_model=os.getenv(
            "GEMINI_ANALYSIS_MODEL", "gemini-2.0-flash-001"
        ).strip(),
        gemini_embedding_model=os.getenv(
            "GEMINI_EMBEDDING_MODEL", "gemini-embedding-001"
        ).strip(),
        max_upload_bytes=int(os.getenv("MAX_UPLOAD_BYTES", str(50 * 1024 * 1024))),
        max_video_seconds=int(os.getenv("MAX_VIDEO_SECONDS", "90")),
    )

