from __future__ import annotations

import unittest
from unittest.mock import patch

from app.services.faiss_index import search_style_embeddings


class StyleIndexTests(unittest.TestCase):
    def test_returns_closest_clip_level_style(self) -> None:
        records = [
            {
                "clip_id": "clip_a",
                "title": "A",
                "style_embedding": [1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
                "style_embedding_version": "style_embedding_v1",
                "style_embedding_dimension": 7,
            },
            {
                "clip_id": "clip_b",
                "title": "B",
                "style_embedding": [0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0],
                "style_embedding_version": "style_embedding_v1",
                "style_embedding_dimension": 7,
            },
        ]

        with patch("app.services.faiss_index.list_clip_style_embeddings", return_value=records):
            result = search_style_embeddings([2.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0])

        self.assertEqual(result["protected_clip_id"], "clip_a")
        self.assertAlmostEqual(result["style_similarity"], 1.0, places=6)
        self.assertTrue(result["style_match"])
        self.assertEqual(len(result["other_style_matches"]), 1)
        self.assertEqual(result["other_style_matches"][0]["protected_clip_id"], "clip_b")
        self.assertAlmostEqual(result["other_style_matches"][0]["style_similarity"], 0.0, places=6)


if __name__ == "__main__":
    unittest.main()
