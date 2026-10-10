"""Gemini visual summary and text embedding helpers."""

from __future__ import annotations

from pathlib import Path

from google import genai
from google.genai import types

from app.config import get_settings


class EmbeddingError(RuntimeError):
    """Represent a failure while creating a content fingerprint."""

    pass


def _client() -> genai.Client:
    """Create a Vertex AI Gen AI client from the application settings."""

    settings = get_settings()
    return genai.Client(
        vertexai=True,
        project=settings.gcp_project_id,
        location=settings.gcp_location,
    )


def _summarize_keyframes(frames: list[Path], duration_seconds: float) -> str:
    """Ask Gemini to turn sampled video frames into a matchable text summary."""

    settings = get_settings()
    prompt = f"""
Create a compact content fingerprint for a short video.
The video is {duration_seconds:.2f} seconds long and the attached images are
evenly spaced keyframes in chronological order.

Describe concrete, matchable details: people, objects, setting, actions,
visible text, logos, colors, and the sequence of events. Include the order of
the keyframes. Focus on what is visibly in the content, not editing style or
legal conclusions. Return plain text in 8 numbered lines, one per keyframe.
""".strip()
    parts = [types.Part.from_bytes(data=frame.read_bytes(), mime_type="image/jpeg") for frame in frames]
    try:
        response = _client().models.generate_content(
            model=settings.gemini_analysis_model,
            contents=[prompt, *parts],
        )
    except Exception as exc:
        raise exc
    summary = (response.text or "").strip()
    if not summary:
        raise EmbeddingError("Gemini returned an empty visual fingerprint")
    return summary


def embed_text(text: str) -> list[float]:
    """Convert a text fingerprint into a normalized-provider embedding vector."""

    settings = get_settings()
    try:
        response = _client().models.embed_content(
            model=settings.gemini_embedding_model,
            contents=text,
            config={
                "task_type": "RETRIEVAL_DOCUMENT",
                "output_dimensionality": 768,
            },
        )
    except Exception as exc:
        raise EmbeddingError("Gemini could not create an embedding") from exc

    embeddings = response.embeddings or []
    values = embeddings[0].values if embeddings else None
    if not values:
        raise EmbeddingError("Gemini returned an empty embedding")
    return [float(value) for value in values]


def embed_video(frames: list[Path], duration_seconds: float) -> list[float]:
    """Build the legacy Day 2 embedding from keyframes and their visual summary."""

    summary = _summarize_keyframes(frames, duration_seconds)
    return embed_text(summary)

