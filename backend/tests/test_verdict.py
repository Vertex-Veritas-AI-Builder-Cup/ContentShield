from __future__ import annotations

import unittest

from app.services.verdict import verdict_from_score


class VerdictTests(unittest.TestCase):
    def test_threshold_boundaries(self) -> None:
        """Verify all public risk labels at their exact threshold boundaries."""

        self.assertEqual(verdict_from_score(0.75), "high_risk")
        self.assertEqual(verdict_from_score(0.50), "medium_risk")
        self.assertEqual(verdict_from_score(0.49), "low_risk")


if __name__ == "__main__":
    unittest.main()
