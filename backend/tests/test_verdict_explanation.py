from __future__ import annotations

import unittest

from app.services.verdict_explanation import (
    VerdictExplanationError,
    validate_verdict_explanation_payload,
)


class VerdictExplanationTests(unittest.TestCase):
    """Protect the stable, frontend-facing shape of model explanations."""

    def test_valid_payload_is_normalized(self) -> None:
        """Keep evidence fields numeric and add a stable explanation identifier."""

        result = validate_verdict_explanation_payload(
            {
                "decision": "likely_match",
                "explanation": "The same subject appears in the same sequence.",
                "confidence_note": "Strong retrieval, but review is still required.",
                "evidence": [
                    {
                        "query_start_seconds": "1.5",
                        "query_end_seconds": 4,
                        "protected_start_seconds": 2,
                        "protected_end_seconds": 4.5,
                        "observation": "The visible composition matches.",
                    }
                ],
                "limitations": ["Audio was not evaluated."],
            },
            model="test-model",
        )

        self.assertTrue(result["verdict_explanation_id"].startswith("explain_"))
        self.assertEqual(result["decision"], "likely_match")
        self.assertEqual(result["evidence"][0]["query_start_seconds"], 1.5)
        self.assertEqual(result["model"], "test-model")

    def test_invalid_decision_is_rejected(self) -> None:
        """Prevent unsupported model labels from reaching the UI or Firestore."""

        with self.assertRaises(VerdictExplanationError):
            validate_verdict_explanation_payload(
                {"decision": "legally_infringing", "explanation": "No."},
                model="test-model",
            )

    def test_invalid_timestamp_is_rejected(self) -> None:
        """Reject malformed evidence timestamps instead of displaying fabricated ranges."""

        with self.assertRaises(VerdictExplanationError):
            validate_verdict_explanation_payload(
                {
                    "decision": "uncertain",
                    "explanation": "The evidence is incomplete.",
                    "evidence": [
                        {
                            "query_start_seconds": -1,
                            "observation": "An observation.",
                        }
                    ],
                },
                model="test-model",
            )


if __name__ == "__main__":
    unittest.main()
