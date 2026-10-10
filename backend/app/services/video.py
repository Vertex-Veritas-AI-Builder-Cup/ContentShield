"""FFmpeg based video inspection used during registration."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from app.config import get_settings


class VideoProcessingError(RuntimeError):
    pass


def probe_video(path: Path) -> dict:
    """Return duration and stream metadata from ffprobe."""

    command = [
        get_settings().ffprobe_binary,
        "-v",
        "error",
        "-show_entries",
        "format=duration:stream=codec_type,width,height",
        "-of",
        "json",
        str(path),
    ]
    try:
        result = subprocess.run(
            command,
            check=True,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError as exc:
        raise VideoProcessingError("ffprobe is not installed") from exc
    except subprocess.CalledProcessError as exc:
        detail = exc.stderr.strip() or "ffprobe could not read the video"
        raise VideoProcessingError(detail) from exc

    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise VideoProcessingError("ffprobe returned invalid metadata") from exc


def video_duration_seconds(path: Path) -> float:
    metadata = probe_video(path)
    try:
        duration = float(metadata["format"]["duration"])
    except (KeyError, TypeError, ValueError) as exc:
        raise VideoProcessingError("Video duration could not be determined") from exc
    if duration <= 0:
        raise VideoProcessingError("Video duration must be greater than zero")
    return duration


def extract_keyframes(path: Path, output_dir: Path, count: int = 8) -> list[Path]:
    """Extract evenly spaced JPEG frames for Gemini's visual fingerprint."""

    output_dir.mkdir(parents=True, exist_ok=True)
    duration = video_duration_seconds(path)
    interval = max(duration / count, 0.1)
    output_pattern = output_dir / "frame-%02d.jpg"
    command = [
        get_settings().ffmpeg_binary,
        "-y",
        "-i",
        str(path),
        "-vf",
        f"fps=1/{interval}",
        "-frames:v",
        str(count),
        "-q:v",
        "3",
        str(output_pattern),
    ]
    try:
        subprocess.run(command, check=True, capture_output=True, text=True)
    except FileNotFoundError as exc:
        raise VideoProcessingError("ffmpeg is not installed") from exc
    except subprocess.CalledProcessError as exc:
        detail = exc.stderr.strip() or "ffmpeg could not extract keyframes"
        raise VideoProcessingError(detail) from exc

    frames = sorted(output_dir.glob("frame-*.jpg"))
    if not frames:
        raise VideoProcessingError("No keyframes were extracted")

    return frames

