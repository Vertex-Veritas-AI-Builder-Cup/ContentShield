"""Application configuration loaded from ``backend/.env``."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


BACKEND_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(BACKEND_ROOT / ".env")


def get_cors_origins() -> list[str]:
    """Return browser origins allowed to call the API, with local defaults."""

    raw = os.getenv(
        "CORS_ORIGINS",
        "http://localhost:3000,http://127.0.0.1:3000",
    )
    return [origin.strip() for origin in raw.split(",") if origin.strip()]


@dataclass(frozen=True)
class Settings:
    gcp_project_id: str
    gcp_location: str
    gcs_bucket: str
    gemini_analysis_model: str
    gemini_embedding_model: str
    gemini_video_embedding_model: str
    gemini_embedding_location: str
    video_embedding_version: str
    video_segment_seconds: int
    video_embedding_concurrency: int
    ffmpeg_binary: str
    ffprobe_binary: str
    max_upload_bytes: int
    max_video_seconds: int
    signed_url_minutes: int


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
        gemini_video_embedding_model=os.getenv(
            "GEMINI_VIDEO_EMBEDDING_MODEL", "gemini-embedding-2"
        ).strip(),
        gemini_embedding_location=os.getenv(
            "GEMINI_EMBEDDING_LOCATION", "global"
        ).strip(),
        video_embedding_version="video_frame_sample_v3",
        video_segment_seconds=int(os.getenv("VIDEO_SEGMENT_SECONDS", "5")),
        video_embedding_concurrency=int(
            os.getenv("VIDEO_EMBEDDING_CONCURRENCY", "8")
        ),
        ffmpeg_binary=os.getenv("FFMPEG_BIN", "ffmpeg").strip() or "ffmpeg",
        ffprobe_binary=os.getenv("FFPROBE_BIN", "ffprobe").strip() or "ffprobe",
        max_upload_bytes=int(os.getenv("MAX_UPLOAD_BYTES", str(50 * 1024 * 1024))),
        max_video_seconds=int(os.getenv("MAX_VIDEO_SECONDS", "90")),
        signed_url_minutes=int(os.getenv("SIGNED_URL_MINUTES", "15")),
    )

