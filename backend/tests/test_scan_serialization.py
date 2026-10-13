from __future__ import annotations

import unittest
from unittest.mock import patch

from app.routes.verdict_explanation import _detail_response


class ScanSerializationTests(unittest.TestCase):
    """Ensure scan detail responses expose evidence without private storage data."""

    @patch("app.routes.verdict_explanation.signed_url_for_gcs_uri")
    @patch("app.routes.verdict_explanation.get_clip")
    def test_detail_response_removes_private_uris_and_embeddings(
        self, get_clip_mock, signed_url_mock
    ) -> None:
        get_clip_mock.return_value = {
            "clip_id": "clip_original",
            "title": "Original",
            "gcs_uri": "gs://private/original.mp4",
            "duration_seconds": 12.0,
        }
        signed_url_mock.side_effect = ["https://signed/original", "https://signed/query"]

        response = _detail_response(
            {
                "scan_id": "scan_1",
                "suspicious_gcs_uri": "gs://private/query.mp4",
                "top_match": {
                    "protected_clip_id": "clip_original",
                    "content_similarity": 0.91,
                    "embedding": [1.0, 2.0],
                },
                "matches": [
                    {
                        "protected_clip_id": "clip_original",
                        "content_similarity": 0.91,
                        "protected_gcs_uri": "gs://private/original.mp4",
                    }
                ],
            }
        )

        self.assertNotIn("suspicious_gcs_uri", response)
        self.assertNotIn("embedding", response["top_match"])
        self.assertNotIn("protected_gcs_uri", response["matches"][0])
        self.assertNotIn("gcs_uri", response["protected_clip"])
        self.assertEqual(response["media"]["protected_video_url"], "https://signed/original")
        self.assertEqual(response["media"]["suspicious_video_url"], "https://signed/query")


if __name__ == "__main__":
    unittest.main()
