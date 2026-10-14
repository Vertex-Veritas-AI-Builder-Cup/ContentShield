from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import patch

from app.routes.scan import _evaluate_style


class ScanPriorityTests(unittest.TestCase):
    def test_style_evaluation_returns_a_match_and_notice(self) -> None:
        with (
            patch("app.routes.scan.extract_style_features", return_value={}),
            patch("app.routes.scan.style_embedding_from_features", return_value=[1.0]),
            patch(
                "app.routes.scan.search_style_embeddings",
                return_value={
                    "protected_clip_id": "clip_1",
                    "protected_title": "Original",
                    "style_similarity": 0.9,
                },
            ),
        ):
            evaluated, skip_reason, match, notice = _evaluate_style(
                Path("sample.mp4"), scan_id="scan_1"
            )

        self.assertTrue(evaluated)
        self.assertIsNone(skip_reason)
        self.assertEqual(match["protected_clip_id"], "clip_1")
        self.assertEqual(notice["type"], "similar_style")


if __name__ == "__main__":
    unittest.main()
