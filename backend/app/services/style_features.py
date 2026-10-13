"""Bounded, content-independent style signals for the Style Match prototype."""

from __future__ import annotations

import math
import re
import subprocess
from pathlib import Path
from statistics import median

from app.config import get_settings
from app.services.video import VideoProcessingError, video_duration_seconds


STYLE_FEATURE_VERSION = "style_features_v1"
STYLE_EMBEDDING_VERSION = "style_embedding_v1"
STYLE_EMBEDDING_DIMENSION = 7
STYLE_MATCH_THRESHOLD = 0.78


class StyleFeatureError(RuntimeError):
    """Raised when a video cannot be analyzed with the bounded style extractor."""


def _detect_scene_cuts(path: Path) -> list[float]:
    """Read coarse scene-change timestamps from FFmpeg's showinfo filter."""

    command = [
        get_settings().ffmpeg_binary,
        "-hide_banner",
        "-i",
        str(path),
        "-vf",
        "select=gt(scene\\,0.35),showinfo",
        "-an",
        "-f",
        "null",
        "-",
    ]
    try:
        result = subprocess.run(command, check=False, capture_output=True, text=True)
    except FileNotFoundError as exc:
        raise StyleFeatureError("ffmpeg is not installed") from exc
    if result.returncode not in {0, 1}:
        detail = result.stderr.strip() or "ffmpeg could not detect scene changes"
        raise StyleFeatureError(detail)
    return [float(value) for value in re.findall(r"pts_time:([0-9]+(?:\\.[0-9]+)?)", result.stderr)]


def _shot_lengths(duration_seconds: float, cuts: list[float]) -> list[float]:
    boundaries = [0.0]
    boundaries.extend(
        sorted(
            {
                round(cut, 3)
                for cut in cuts
                if 0.05 < cut < duration_seconds - 0.05
            }
        )
    )
    boundaries.append(duration_seconds)
    return [round(end - start, 3) for start, end in zip(boundaries, boundaries[1:])]


def _shot_histogram(lengths: list[float]) -> list[float]:
    bins = (1.0, 2.0, 4.0, 8.0)
    counts = [0, 0, 0, 0, 0]
    for length in lengths:
        index = next((position for position, bound in enumerate(bins) if length < bound), 4)
        counts[index] += 1
    total = float(len(lengths)) or 1.0
    return [round(count / total, 6) for count in counts]


def _hook_type(transcript: str) -> str:
    """Classify only explicit transcript cues; never infer a hook from pixels."""

    text = transcript.strip().lower()
    if not text:
        return "unavailable"
    if "?" in text or any(word in text for word in ("did you know", "how to", "why ")):
        return "question"
    if any(word in text for word in ("percent", "%", "number", "statistic")):
        return "statistic"
    if any(word in text for word in ("today i", "watch me", "i will", "let me")):
        return "direct_address"
    if any(word in text for word in ("story", "when i", "once ")):
        return "story"
    return "other"


def extract_style_features(path: Path, *, transcript: str = "") -> dict:
    """Extract a small style signature without reusing content embeddings."""

    try:
        duration = video_duration_seconds(path)
    except VideoProcessingError as exc:
        raise StyleFeatureError(str(exc)) from exc
    if duration <= 0 or not math.isfinite(duration):
        raise StyleFeatureError("Video duration must be finite and greater than zero")

    cuts = _detect_scene_cuts(path)
    lengths = _shot_lengths(duration, cuts)
    cuts_per_minute = len(cuts) / duration * 60.0
    return {
        "style_feature_version": STYLE_FEATURE_VERSION,
        "duration_seconds": round(duration, 3),
        "pacing": {
            "cut_count": len(cuts),
            "cuts_per_minute": round(cuts_per_minute, 3),
            "mean_shot_seconds": round(sum(lengths) / len(lengths), 3),
            "median_shot_seconds": round(float(median(lengths)), 3),
            "shot_length_histogram": _shot_histogram(lengths),
        },
        "opening_hook": {
            "type": _hook_type(transcript),
            "source": "transcript" if transcript.strip() else "unavailable",
        },
        "overlay_pattern": {
            "status": "not_analyzed",
            "positions": [],
        },
        "transcript_timing": {
            "status": "provided_without_timing" if transcript.strip() else "not_provided",
        },
        "limitations": [
            "Scene cuts are estimated with a fixed FFmpeg threshold.",
            "Overlay positions require OCR and are not analyzed in this prototype.",
            "Hook classification is available only when a transcript is supplied.",
        ],
    }


def style_embedding_from_features(features: dict) -> list[float]:
    """Build a normalized-shape, clip-level vector from editing-style signals.

    The vector intentionally excludes visual/content embeddings. It captures
    coarse pacing and shot-length distribution so it can be stored once for a
    protected clip and compared lazily during a scan.
    """

    pacing = features.get("pacing") or {}
    histogram = pacing.get("shot_length_histogram") or []
    if len(histogram) != 5:
        raise StyleFeatureError("Style shot-length histogram must have five bins")

    vector = [
        min(max(float(pacing.get("cuts_per_minute") or 0.0) / 120.0, 0.0), 1.0),
        min(max(float(pacing.get("median_shot_seconds") or 0.0) / 10.0, 0.0), 1.0),
        *[min(max(float(value), 0.0), 1.0) for value in histogram],
    ]
    if len(vector) != STYLE_EMBEDDING_DIMENSION or not all(math.isfinite(value) for value in vector):
        raise StyleFeatureError("Style embedding contains invalid values")
    return [round(value, 6) for value in vector]


def _similarity(left: float, right: float) -> float:
    if left == 0 and right == 0:
        return 1.0
    scale = max(abs(left), abs(right), 1e-9)
    return max(0.0, 1.0 - abs(left - right) / scale)


def _cosine(left: list[float], right: list[float]) -> float:
    numerator = sum(a * b for a, b in zip(left, right))
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if not left_norm or not right_norm:
        return 0.0
    return max(0.0, min(1.0, numerator / (left_norm * right_norm)))


def compare_style_features(query: dict, reference: dict) -> dict:
    """Compare style-only signals and label the result as creator intelligence."""

    query_pacing = query.get("pacing") or {}
    reference_pacing = reference.get("pacing") or {}
    pace_scores = {
        "cut_rhythm": _similarity(
            float(query_pacing.get("cuts_per_minute") or 0),
            float(reference_pacing.get("cuts_per_minute") or 0),
        ),
        "shot_length": _similarity(
            float(query_pacing.get("median_shot_seconds") or 0),
            float(reference_pacing.get("median_shot_seconds") or 0),
        ),
        "shot_length_distribution": _cosine(
            query_pacing.get("shot_length_histogram") or [],
            reference_pacing.get("shot_length_histogram") or [],
        ),
    }
    signals = [
        {
            "name": name,
            "available": True,
            "score": round(score, 4),
            "evidence": "Editing pace and shot-length signatures are similar."
            if score >= 0.75
            else "Editing pace differs in this comparison.",
        }
        for name, score in pace_scores.items()
    ]

    query_hook = (query.get("opening_hook") or {}).get("type")
    reference_hook = (reference.get("opening_hook") or {}).get("type")
    if query_hook != "unavailable" and reference_hook != "unavailable":
        hook_score = 1.0 if query_hook == reference_hook else 0.0
        signals.append(
            {
                "name": "opening_hook",
                "available": True,
                "score": hook_score,
                "evidence": f"Both videos classify as {query_hook}."
                if hook_score
                else "The supplied transcripts classify the openings differently.",
            }
        )
    else:
        signals.append(
            {
                "name": "opening_hook",
                "available": False,
                "score": None,
                "evidence": "Transcript timing was not available for both videos.",
            }
        )

    available = [signal["score"] for signal in signals if signal["available"]]
    if not available:
        raise StyleFeatureError("No comparable style signals are available")
    score = sum(available) / len(available)
    if score >= 0.78:
        assessment = "format_clone_candidate"
    elif score >= 0.55:
        assessment = "possible_style_overlap"
    else:
        assessment = "low_style_similarity"
    return {
        "style_similarity": round(score, 4),
        "assessment": assessment,
        "signals": signals,
        "evidence": [signal["evidence"] for signal in signals if signal["available"]],
        "limitations": sorted(
            set(query.get("limitations", []))
            | set(reference.get("limitations", []))
            | {"Style similarity is not a copyright or legal conclusion."}
        ),
        "disclaimer": "Prototype creator-intelligence signal, not a copyright or legal conclusion; review the underlying videos before acting.",
    }
