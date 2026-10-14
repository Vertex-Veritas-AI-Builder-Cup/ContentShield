"""Direct video-segment embeddings for content matching."""

from __future__ import annotations

import math
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from google import genai
from google.genai import types

from app.config import get_settings


class VideoEmbeddingError(RuntimeError):
    """Raised when a video segment cannot be embedded."""


MAX_VIDEO_EMBEDDING_CONCURRENCY = 8
MIN_VIDEO_EMBEDDING_FRAMES = 20


def _client() -> genai.Client:
    """Create the Vertex AI client used for direct video embeddings."""

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
    """Extract and validate the numeric embedding values from an SDK response."""

    embeddings = getattr(response, "embeddings", None) or []
    values = getattr(embeddings[0], "values", None) if embeddings else None
    if not values:
        raise VideoEmbeddingError("Gemini returned an empty video embedding")
    return [float(value) for value in values]


def _embed_segment(
    gcs_uri: str,
    *,
    start_seconds: float,
    end_seconds: float,
    segment_number: int,
    fps: float,
    mime_type: str,
    model: str,
) -> list[float]:
    """Request one segment embedding with an isolated SDK client."""

    content = types.Content(
        parts=[
            types.Part(
                file_data=types.FileData(
                    file_uri=gcs_uri,
                    mime_type=mime_type,
                ),
                video_metadata=types.VideoMetadata(
                    fps=fps,
                    start_offset=_format_offset(start_seconds),
                    end_offset=_format_offset(end_seconds),
                ),
            )
        ]
    )
    client: genai.Client | None = None
    try:
        client = _client()
        response = client.models.embed_content(
            model=model,
            contents=[content],
        )
        return _embedding_values(response)
    except VideoEmbeddingError:
        raise
    except Exception as exc:
        raise VideoEmbeddingError(
            f"Could not embed video segment {segment_number}"
        ) from exc
    finally:
        if client is not None:
            try:
                client.close()
            except Exception:
                pass


def embed_video_segments(
    gcs_uri: str,
    *,
    duration_seconds: float,
    mime_type: str,
) -> list[dict]:
    """Create ordered segment embeddings with bounded parallel requests.

    The provider calls run concurrently, but the returned list remains ordered
    by segment number so downstream matching and evidence timestamps are stable.
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
    if settings.video_embedding_version != "video_frame_sample_v2":
        raise VideoEmbeddingError(
            f"Unsupported video embedding version: {settings.video_embedding_version}"
        )
    segment_seconds = settings.video_segment_seconds
    if segment_seconds <= 0:
        raise VideoEmbeddingError("VIDEO_SEGMENT_SECONDS must be greater than zero")
    if settings.video_embedding_concurrency <= 0:
        raise VideoEmbeddingError(
            "VIDEO_EMBEDDING_CONCURRENCY must be greater than zero"
        )

    configured_segment_count = math.ceil(duration_seconds / segment_seconds)
    segment_count = max(MIN_VIDEO_EMBEDDING_FRAMES, configured_segment_count)
    window_seconds = duration_seconds / segment_count
    segment_specs = [
        (number, number * window_seconds, (number + 1) * window_seconds)
        for number in range(segment_count)
    ]

    worker_count = min(
        settings.video_embedding_concurrency,
        MAX_VIDEO_EMBEDDING_CONCURRENCY,
        len(segment_specs),
    )

    def embed_spec(spec: tuple[int, float, float]) -> list[float]:
        number, segment_start, segment_end = spec
        return _embed_segment(
            gcs_uri,
            start_seconds=segment_start,
            end_seconds=segment_end,
            segment_number=number,
            fps=max(0.5, 1.0 / (segment_end - segment_start)),
            mime_type=mime_type,
            model=settings.gemini_video_embedding_model,
        )

    with ThreadPoolExecutor(max_workers=worker_count) as executor:
        values_by_segment = list(executor.map(embed_spec, segment_specs))

    embedding_dimension = len(values_by_segment[0])
    if embedding_dimension <= 0:
        raise VideoEmbeddingError("Gemini returned an empty video embedding")
    for values in values_by_segment:
        if len(values) != embedding_dimension:
            raise VideoEmbeddingError(
                "Video embedding dimensions changed between segments"
            )

    return [
        {
            "segment_id": f"segment_{number:03d}",
            "start_offset_seconds": segment_start,
            "end_offset_seconds": segment_end,
            "embedding": values,
        }
        for (number, segment_start, segment_end), values in zip(
            segment_specs, values_by_segment
        )
    ]
