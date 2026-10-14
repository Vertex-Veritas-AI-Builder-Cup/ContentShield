from __future__ import annotations

import unittest
from unittest.mock import patch

from app.routes.verdict_explanation import DmcaRequest, _detail_response, create_dmca_draft


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

    @patch("app.routes.verdict_explanation.signed_url_for_gcs_uri")
    @patch("app.routes.verdict_explanation.get_clip")
    def test_detail_response_uses_style_matches_own_original_video(
        self, get_clip_mock, signed_url_mock
    ) -> None:
        """Return the style-matched original rather than reusing the content-match video."""

        get_clip_mock.side_effect = [
            {"clip_id": "content_clip", "gcs_uri": "gs://private/content.mp4"},
            {"clip_id": "style_clip", "gcs_uri": "gs://private/style.mp4"},
        ]
        signed_url_mock.side_effect = [
            "https://signed/content",
            "https://signed/style",
            "https://signed/checked",
        ]

        response = _detail_response(
            {
                "scan_id": "scan_1",
                "suspicious_gcs_uri": "gs://private/checked.mp4",
                "top_match": {"protected_clip_id": "content_clip"},
                "style_match": {"protected_clip_id": "style_clip", "style_similarity": 0.9},
                "matches": [],
            }
        )

        self.assertEqual(response["media"]["protected_video_url"], "https://signed/content")
        self.assertEqual(response["media"]["style_original_video_url"], "https://signed/style")
        self.assertEqual(response["media"]["suspicious_video_url"], "https://signed/checked")

    @patch("app.routes.verdict_explanation.save_dmca_draft")
    @patch("app.routes.verdict_explanation.generate_dmca_draft")
    @patch("app.routes.verdict_explanation.signed_url_for_gcs_uri")
    @patch("app.routes.verdict_explanation.get_clip")
    @patch("app.routes.verdict_explanation._load_scan_or_404")
    def test_dmca_draft_receives_signed_evidence_urls(
        self,
        load_scan_mock,
        get_clip_mock,
        signed_url_mock,
        generate_mock,
        save_mock,
    ) -> None:
        """Use freshly generated signed links without exposing private GCS URIs."""

        load_scan_mock.return_value = {
            "top_match": {"protected_clip_id": "clip_original"},
            "suspicious_gcs_uri": "gs://private/query.mp4",
            "verdict_explanation": {"explanation": "Evidence exists."},
        }
        get_clip_mock.return_value = {"gcs_uri": "gs://private/original.mp4"}
        signed_url_mock.side_effect = ["https://signed/original", "https://signed/query"]
        generate_mock.return_value = {"draft_id": "dmca_1"}

        response = create_dmca_draft("scan_1", DmcaRequest())

        self.assertEqual(response["dmca_draft"]["draft_id"], "dmca_1")
        self.assertEqual(
            generate_mock.call_args.kwargs["protected_media_url"],
            "https://signed/original",
        )
        self.assertEqual(
            generate_mock.call_args.kwargs["suspicious_media_url"],
            "https://signed/query",
        )
        save_mock.assert_called_once_with("scan_1", {"draft_id": "dmca_1"})


if __name__ == "__main__":
    unittest.main()
