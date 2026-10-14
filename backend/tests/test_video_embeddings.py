from __future__ import annotations

import threading
import time
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from app.services.video_embeddings import embed_video_segments


class VideoEmbeddingConcurrencyTests(unittest.TestCase):
    """Ensure segment requests are parallel but remain bounded and ordered."""

    def test_segment_requests_use_bounded_parallelism(self) -> None:
        settings = SimpleNamespace(
            gemini_video_embedding_model="video-model",
            gemini_embedding_location="global",
            video_embedding_version="video_segment_v1",
            video_segment_seconds=5,
            video_embedding_concurrency=2,
        )
        lock = threading.Lock()
        active = 0
        maximum_active = 0

        def fake_embed_segment(*args, **kwargs):
            nonlocal active, maximum_active
            with lock:
                active += 1
                maximum_active = max(maximum_active, active)
            time.sleep(0.03)
            with lock:
                active -= 1
            return [float(kwargs["segment_number"])]

        with (
            patch("app.services.video_embeddings.get_settings", return_value=settings),
            patch(
                "app.services.video_embeddings._embed_segment",
                side_effect=fake_embed_segment,
            ),
        ):
            result = embed_video_segments(
                "gs://bucket/video.mp4",
                duration_seconds=12,
                mime_type="video/mp4",
            )

        self.assertEqual(
            [item["segment_id"] for item in result],
            ["segment_000", "segment_001", "segment_002"],
        )
        self.assertEqual(
            [item["embedding"] for item in result],
            [[0.0], [1.0], [2.0]],
        )
        self.assertGreater(maximum_active, 1)
        self.assertLessEqual(maximum_active, 2)


if __name__ == "__main__":
    unittest.main()
