from __future__ import annotations

import unittest
from dataclasses import replace
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.config import get_settings
from app.main import app
from app.services.faiss_index import SearchIndexError


class ScanValidationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        """Create one FastAPI test client and load shared backend settings."""

        cls.client = TestClient(app)
        cls.settings = get_settings()

    def test_unsupported_type_returns_400(self) -> None:
        """Ensure unsupported upload types are rejected before processing."""

        response = self.client.post(
            "/api/scan",
            files={"file": ("notes.txt", b"not a video", "text/plain")},
        )
        self.assertEqual(response.status_code, 400)

    def test_oversized_upload_returns_400(self) -> None:
        """Ensure uploads exceeding the configured byte limit return a client error."""

        settings = replace(self.settings, max_upload_bytes=1)
        with patch("app.routes.scan.get_settings", return_value=settings):
            response = self.client.post(
                "/api/scan",
                files={"file": ("scan.mp4", b"12", "video/mp4")},
            )
        self.assertEqual(response.status_code, 400)

    def test_overlong_video_returns_400(self) -> None:
        """Ensure videos longer than the configured duration limit are rejected."""

        with (
            patch("app.routes.scan.get_settings", return_value=self.settings),
            patch("app.routes.scan.video_duration_seconds", return_value=91.0),
        ):
            response = self.client.post(
                "/api/scan",
                files={"file": ("scan.mp4", b"video", "video/mp4")},
            )
        self.assertEqual(response.status_code, 400)

    def test_empty_catalog_returns_422(self) -> None:
        """Ensure scanning fails clearly when no compatible protected clips exist."""

        with (
            patch("app.routes.scan.get_settings", return_value=self.settings),
            patch("app.routes.scan.video_duration_seconds", return_value=1.0),
            patch(
                "app.routes.scan.build_segment_index",
                side_effect=SearchIndexError("No compatible protected video embeddings are available"),
            ),
        ):
            response = self.client.post(
                "/api/scan",
                files={"file": ("scan.mp4", b"video", "video/mp4")},
            )
        self.assertEqual(response.status_code, 422)


if __name__ == "__main__":
    unittest.main()
