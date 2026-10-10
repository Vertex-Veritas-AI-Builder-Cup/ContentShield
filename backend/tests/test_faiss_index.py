from __future__ import annotations

import unittest
from unittest.mock import patch

import numpy as np

from app.services.faiss_index import search_video_segments


class FaissIndexTests(unittest.TestCase):
    @staticmethod
    def _record(clip_id: str, segment_id: str, embedding: list[float]) -> dict:
        return {
            "clip_id": clip_id,
            "title": clip_id.replace("_", " ").title(),
            "segment_id": segment_id,
            "start_offset_seconds": 0.0,
            "end_offset_seconds": 5.0,
            "embedding": embedding,
            "embedding_version": "video_segment_v1",
            "embedding_model": "gemini-embedding-2",
            "embedding_dimension": len(embedding),
        }

    def test_faiss_score_matches_cosine_similarity(self) -> None:
        records = [
            {
                "clip_id": "clip_a",
                "title": "A",
                "segment_id": "segment_000",
                "start_offset_seconds": 0.0,
                "end_offset_seconds": 5.0,
                "embedding": [1.0, 0.0],
                "embedding_version": "video_segment_v1",
                "embedding_model": "gemini-embedding-2",
                "embedding_dimension": 2,
            },
            {
                "clip_id": "clip_b",
                "title": "B",
                "segment_id": "segment_000",
                "start_offset_seconds": 0.0,
                "end_offset_seconds": 5.0,
                "embedding": [0.0, 1.0],
                "embedding_version": "video_segment_v1",
                "embedding_model": "gemini-embedding-2",
                "embedding_dimension": 2,
            },
        ]
        query = np.asarray([2.0, 1.0], dtype=np.float32)
        expected = float(np.dot(query / np.linalg.norm(query), np.asarray([1.0, 0.0])))

        with patch("app.services.faiss_index.list_clip_segment_embeddings", return_value=records):
            results = search_video_segments(
                [{"segment_id": "segment_000", "embedding": query.tolist()}],
                limit=2,
            )

        self.assertEqual([result["protected_clip_id"] for result in results], ["clip_a", "clip_b"])
        self.assertAlmostEqual(results[0]["content_similarity"], expected, places=6)

    def test_cropped_copy_keeps_high_risk_with_partial_coverage(self) -> None:
        records = [
            self._record("clip_original", "segment_000", [1.0, 0.0]),
            self._record("clip_other", "segment_000", [0.0, -1.0]),
        ]

        with patch("app.services.faiss_index.list_clip_segment_embeddings", return_value=records):
            results = search_video_segments(
                [
                    {"segment_id": "segment_000", "embedding": [1.0, 0.0]},
                    {"segment_id": "segment_001", "embedding": [0.6, 0.8]},
                ]
            )

        top = results[0]
        self.assertEqual(top["protected_clip_id"], "clip_original")
        self.assertEqual(top["verdict"], "high_risk")
        self.assertAlmostEqual(top["content_similarity"], 0.8, places=6)
        self.assertEqual(top["matched_segment_count"], 1)
        self.assertAlmostEqual(top["segment_coverage"], 0.5, places=6)

    def test_unrelated_video_is_low_risk(self) -> None:
        records = [
            self._record("clip_a", "segment_000", [1.0, 0.0]),
            self._record("clip_b", "segment_000", [0.0, 1.0]),
        ]

        with patch("app.services.faiss_index.list_clip_segment_embeddings", return_value=records):
            results = search_video_segments(
                [{"segment_id": "segment_000", "embedding": [0.0, -1.0]}]
            )

        self.assertEqual(results[0]["verdict"], "low_risk")
        self.assertLess(results[0]["content_similarity"], 0.50)


if __name__ == "__main__":
    unittest.main()
