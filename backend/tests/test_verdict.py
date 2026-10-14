from __future__ import annotations

import unittest

from app.services.verdict import (
    HIGH_RISK_THRESHOLD,
    content_score_from_cosine,
    verdict_from_score,
)


class VerdictTests(unittest.TestCase):
    def test_threshold_boundaries(self) -> None:
        """Verify all public risk labels at their exact threshold boundaries."""

        self.assertEqual(verdict_from_score(HIGH_RISK_THRESHOLD), "high_risk")
        self.assertEqual(verdict_from_score(0.50), "medium_risk")
        self.assertEqual(verdict_from_score(0.49), "low_risk")

    def test_content_score_is_bounded_and_centered(self) -> None:
        """The public score is bounded while preserving cosine ordering."""

        self.assertEqual(content_score_from_cosine(-1.0), 0.0)
        self.assertEqual(content_score_from_cosine(0.60), 0.0)
        self.assertGreater(content_score_from_cosine(0.70), 0.0)
        self.assertLess(content_score_from_cosine(0.70), 1.0)
        self.assertLessEqual(content_score_from_cosine(1.0), 1.0)


if __name__ == "__main__":
    unittest.main()
