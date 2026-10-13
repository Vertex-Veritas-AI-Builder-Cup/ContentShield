from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import patch

from app.services.style_features import compare_style_features, extract_style_features


def _features(*, cuts_per_minute: float, median_shot_seconds: float, hook: str = "unavailable") -> dict:
    return {
        "style_feature_version": "style_features_v1",
        "pacing": {
            "cuts_per_minute": cuts_per_minute,
            "median_shot_seconds": median_shot_seconds,
            "shot_length_histogram": [0.0, 1.0, 0.0, 0.0, 0.0],
        },
        "opening_hook": {"type": hook},
        "limitations": ["OCR is unavailable."],
    }


class StyleFeatureTests(unittest.TestCase):
    def test_extractor_keeps_style_features_separate_and_bounded(self) -> None:
        with (
            patch("app.services.style_features.video_duration_seconds", return_value=10.0),
            patch("app.services.style_features._detect_scene_cuts", return_value=[2.0, 5.0, 8.0]),
        ):
            result = extract_style_features(Path("sample.mp4"), transcript="Did you know this?")

        self.assertEqual(result["style_feature_version"], "style_features_v1")
        self.assertEqual(result["pacing"]["cut_count"], 3)
        self.assertEqual(result["opening_hook"]["type"], "question")
        self.assertNotIn("embedding", result)

    def test_matching_pacing_is_a_format_clone_candidate(self) -> None:
        comparison = compare_style_features(
            _features(cuts_per_minute=30, median_shot_seconds=2, hook="question"),
            _features(cuts_per_minute=30, median_shot_seconds=2, hook="question"),
        )

        self.assertEqual(comparison["assessment"], "format_clone_candidate")
        self.assertGreaterEqual(comparison["style_similarity"], 0.78)
        self.assertIn("not a copyright", comparison["disclaimer"])

    def test_unavailable_hook_does_not_become_a_zero_score(self) -> None:
        comparison = compare_style_features(
            _features(cuts_per_minute=30, median_shot_seconds=2),
            _features(cuts_per_minute=30, median_shot_seconds=2),
        )

        hook = next(signal for signal in comparison["signals"] if signal["name"] == "opening_hook")
        self.assertFalse(hook["available"])
        self.assertGreaterEqual(comparison["style_similarity"], 0.99)


if __name__ == "__main__":
    unittest.main()
