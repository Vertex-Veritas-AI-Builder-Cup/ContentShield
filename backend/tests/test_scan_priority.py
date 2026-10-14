from __future__ import annotations

import unittest

from app.routes.scan import _should_evaluate_style


class ScanPriorityTests(unittest.TestCase):
    def test_style_runs_without_a_content_match(self) -> None:
        self.assertTrue(_should_evaluate_style(None))
        self.assertTrue(_should_evaluate_style({"content_similarity": 0.74}))

    def test_style_also_runs_for_a_high_content_match(self) -> None:
        self.assertTrue(_should_evaluate_style({"content_similarity": 0.75}))
        self.assertTrue(_should_evaluate_style({"content_similarity": 0.91}))


if __name__ == "__main__":
    unittest.main()
