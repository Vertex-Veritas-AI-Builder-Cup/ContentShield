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


if __name__ == "__main__":
    unittest.main()
