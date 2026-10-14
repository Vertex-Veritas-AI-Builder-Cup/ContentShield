from __future__ import annotations

import unittest
from datetime import datetime, timezone
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.config import get_settings
from app.main import app


class ClipRegistrationTests(unittest.TestCase):
    """Ensure registration returns after upload instead of waiting for fingerprints."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.client = TestClient(app)
        cls.settings = get_settings()

    def test_registration_returns_processing_before_background_fingerprinting(self) -> None:
        """Return 200 with a pending status and schedule the expensive work."""

        def finish_background(**kwargs):
            kwargs["temp_path"].unlink(missing_ok=True)

        with (
            patch("app.routes.clips.get_settings", return_value=self.settings),
            patch("app.routes.clips.video_duration_seconds", return_value=1.0),
            patch("app.routes.clips.upload_file", return_value="gs://bucket/original.mp4"),
            patch(
                "app.routes.clips.save_pending_clip",
                return_value=datetime.now(timezone.utc),
            ),
            patch(
                "app.routes.clips._fingerprint_clip_in_background",
                side_effect=finish_background,
            ) as background_mock,
        ):
            response = self.client.post(
                "/api/clips/register",
                files={"file": ("original.mp4", b"video", "video/mp4")},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "processing")
        background_mock.assert_called_once()

    def test_move_scan_to_originals_reuses_scan_embedding(self) -> None:
        """Promote a completed scan without embedding the same video again."""

        with (
            patch(
                "app.routes.clips.get_scan",
                return_value={
                    "scan_id": "scan_1",
                    "suspicious_gcs_uri": "gs://bucket/suspicious/query.mp4",
                    "source_filename": "query.mp4",
                    "content_type": "video/mp4",
                    "suspicious_duration_seconds": 8.0,
                },
            ),
            patch(
                "app.routes.clips.get_scan_embedding",
                return_value={
                    "embedding_segments": [
                        {
                            "segment_id": "segment_000",
                            "start_offset_seconds": 0.0,
                            "end_offset_seconds": 8.0,
                            "embedding": [1.0, 0.0],
                        }
                    ],
                    "embedding_version": self.settings.video_embedding_version,
                    "embedding_model": self.settings.gemini_video_embedding_model,
                    "embedding_dimension": 2,
                },
            ),
            patch("app.routes.clips.get_settings", return_value=self.settings),
            patch(
                "app.routes.clips.move_gcs_uri",
                return_value="gs://bucket/originals/clip_1.mp4",
            ) as move_mock,
            patch(
                "app.routes.clips.save_pending_clip",
                return_value=datetime.now(timezone.utc),
            ) as save_pending_mock,
            patch("app.routes.clips.finalize_clip") as finalize_mock,
            patch(
                "app.routes.clips.save_scan_promotion",
                return_value=datetime.now(timezone.utc),
            ) as save_promotion_mock,
        ):
            response = self.client.post(
                "/api/scans/scan_1/move-to-original",
                json={"title": "New original", "creator_name": "A Creator"},
            )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["title"], "New original")
        self.assertEqual(payload["status"], "fingerprinted")
        move_mock.assert_called_once()
        self.assertEqual(move_mock.call_args.args[0], "gs://bucket/suspicious/query.mp4")
        self.assertRegex(move_mock.call_args.args[1], r"^originals/clip_[a-f0-9]{12}\.mp4$")
        self.assertEqual(save_pending_mock.call_args.kwargs["title"], "New original")
        self.assertEqual(save_pending_mock.call_args.kwargs["creator_name"], "A Creator")
        finalize_mock.assert_called_once()
        self.assertEqual(
            finalize_mock.call_args.kwargs["embedding_segments"][0]["embedding"],
            [1.0, 0.0],
        )
        save_promotion_mock.assert_called_once()


if __name__ == "__main__":
    unittest.main()
