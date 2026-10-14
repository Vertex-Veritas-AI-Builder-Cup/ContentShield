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

    def test_move_scan_to_originals_creates_pending_catalog_clip(self) -> None:
        """Promote a stored suspicious upload and schedule its fingerprints."""

        def download_to_temp(_uri, target):
            target.write_bytes(b"video")

        def finish_background(**kwargs):
            kwargs["temp_path"].unlink(missing_ok=True)

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
                "app.routes.clips.move_gcs_uri",
                return_value="gs://bucket/originals/clip_1.mp4",
            ) as move_mock,
            patch("app.routes.clips.download_gcs_uri", side_effect=download_to_temp),
            patch(
                "app.routes.clips.save_pending_clip",
                return_value=datetime.now(timezone.utc),
            ) as save_pending_mock,
            patch(
                "app.routes.clips.save_scan_promotion",
                return_value=datetime.now(timezone.utc),
            ) as save_promotion_mock,
            patch(
                "app.routes.clips._fingerprint_clip_in_background",
                side_effect=finish_background,
            ) as background_mock,
        ):
            response = self.client.post(
                "/api/scans/scan_1/move-to-original",
                json={"title": "New original", "creator_name": "A Creator"},
            )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["title"], "New original")
        self.assertEqual(payload["status"], "processing")
        move_mock.assert_called_once()
        self.assertEqual(move_mock.call_args.args[0], "gs://bucket/suspicious/query.mp4")
        self.assertRegex(move_mock.call_args.args[1], r"^originals/clip_[a-f0-9]{12}\.mp4$")
        self.assertEqual(save_pending_mock.call_args.kwargs["title"], "New original")
        self.assertEqual(save_pending_mock.call_args.kwargs["creator_name"], "A Creator")
        save_promotion_mock.assert_called_once()
        background_mock.assert_called_once()


if __name__ == "__main__":
    unittest.main()
