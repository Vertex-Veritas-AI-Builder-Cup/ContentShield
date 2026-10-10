"""Direct video-segment embeddings for content matching."""

from __future__ import annotations

import math
from typing import Any

from google import genai
from google.genai import types

from app.config import get_settings


class VideoEmbeddingError(RuntimeError):
    """Raised when a video segment cannot be embedded."""


def _client() -> genai.Client:
    settings = get_settings()
    return genai.Client(
        vertexai=True,
        project=settings.gcp_project_id,
        location=settings.gemini_embedding_location,
    )


def _format_offset(seconds: float) -> str:
    """Format a video offset in the duration form accepted by the SDK."""

    return f"{seconds:.3f}s"


def _embedding_values(response: Any) -> list[float]:
    embeddings = getattr(response, "embeddings", None) or []
    values = getattr(embeddings[0], "values", None) if embeddings else None
    if not values:
        raise VideoEmbeddingError("Gemini returned an empty video embedding")
    return [float(value) for value in values]


def embed_video_segments(
    gcs_uri: str,
    *,
    duration_seconds: float,
    mime_type: str,
) -> list[dict]:
    """Create one direct multimodal embedding for each video segment.

    The protected and suspicious paths call this function with the same model,
    segment length, and input format. The returned vectors are intentionally
    provider-neutral so the FAISS layer does not depend on the Gen AI SDK.
    """

    if not gcs_uri.startswith("gs://"):
        raise VideoEmbeddingError("Video embedding requires a GCS URI")
    if duration_seconds <= 0 or not math.isfinite(duration_seconds):
        raise VideoEmbeddingError("Video duration must be greater than zero")
    if mime_type not in {"video/mp4", "video/quicktime"}:
        raise VideoEmbeddingError("Only MP4 and MOV videos are supported")

    settings = get_settings()
    if not settings.gemini_video_embedding_model:
        raise VideoEmbeddingError("Video embedding model is not configured")
    if not settings.gemini_embedding_location:
        raise VideoEmbeddingError("Video embedding location is not configured")
    if settings.video_embedding_version != "video_segment_v1":
        raise VideoEmbeddingError(
            f"Unsupported video embedding version: {settings.video_embedding_version}"
        )
    segment_seconds = settings.video_segment_seconds
    if segment_seconds <= 0:
        raise VideoEmbeddingError("VIDEO_SEGMENT_SECONDS must be greater than zero")

    client = _client()
    segments: list[dict] = []
    embedding_dimension: int | None = None
    start = 0.0
    segment_number = 0

    while start < duration_seconds:
        end = min(start + segment_seconds, duration_seconds)
        content = types.Content(
            parts=[
                types.Part(
                    file_data=types.FileData(
                        file_uri=gcs_uri,
                        mime_type=mime_type,
                    ),
                    video_metadata=types.VideoMetadata(
                        fps=0.5,
                        start_offset=_format_offset(start),
                        end_offset=_format_offset(end),
                    ),
                )
            ]
        )
        try:
            response = client.models.embed_content(
                model=settings.gemini_video_embedding_model,
                contents=[content],
            )
            values = _embedding_values(response)
            if embedding_dimension is None:
                embedding_dimension = len(values)
            elif len(values) != embedding_dimension:
                raise VideoEmbeddingError(
                    "Video embedding dimensions changed between segments"
                )
        except VideoEmbeddingError:
            raise
        except Exception as exc:
            raise VideoEmbeddingError(
                f"Could not embed video segment {segment_number}"
            ) from exc

        segments.append(
            {
                "segment_id": f"segment_{segment_number:03d}",
                "start_offset_seconds": start,
                "end_offset_seconds": end,
                "embedding": values,
            }
        )
        segment_number += 1
        start = end

    return segments
