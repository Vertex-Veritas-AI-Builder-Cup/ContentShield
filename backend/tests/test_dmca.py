from __future__ import annotations

import unittest

from app.services.dmca import DmcaDraftError, generate_dmca_draft


class DmcaDraftTests(unittest.TestCase):
    """Ensure notice drafts stay factual and require stored evidence."""

    def test_complete_evidence_creates_reviewable_draft(self) -> None:
        """Include similarity, explanation, timestamps, and the legal-review disclaimer."""

        draft = generate_dmca_draft(
            scan={"top_match": {"protected_title": "Original", "content_similarity": 0.91}},
            verdict_explanation={
                "decision": "likely_match",
                "explanation": "The same sequence is visible.",
                "evidence": [
                    {
                        "query_start_seconds": 1,
                        "query_end_seconds": 5,
                        "protected_start_seconds": 2,
                        "protected_end_seconds": 6,
                        "observation": "The same subject and text appear.",
                    }
                ],
                "limitations": ["Audio was not evaluated."],
            },
            creator_name="A Creator",
            creator_email="creator@example.com",
            platform="Example Platform",
            original_url="https://example.com/original-video",
            infringing_url="https://example.com/copied-video",
            protected_media_url="https://signed/original",
            suspicious_media_url="https://signed/suspicious",
        )

        self.assertIn("Similarity score: 0.910", draft["body"])
        self.assertIn("same subject and text", draft["body"])
        self.assertIn("Original URL: https://exampl", draft["body"])
        self.assertIn("Potentially infringing URL: https://exampl", draft["body"])
        self.assertIn("Protected original video: https://signed/", draft["body"])
        self.assertIn("Suspicious video: https://signed/", draft["body"])
        self.assertEqual(draft["disclaimer"], "Draft for creator and legal review; not legal advice.")

    def test_missing_explanation_is_rejected(self) -> None:
        """Do not produce a notice when the scan lacks a usable verdict explanation."""

        with self.assertRaises(DmcaDraftError):
            generate_dmca_draft(scan={"top_match": {"content_similarity": 0.9}}, verdict_explanation={})

    def test_missing_top_match_is_rejected(self) -> None:
        """Do not produce a notice when retrieval found no protected content."""

        with self.assertRaises(DmcaDraftError):
            generate_dmca_draft(scan={"top_match": None}, verdict_explanation={"explanation": "No match."})

    def test_selected_match_can_drive_a_draft_without_being_top_match(self) -> None:
        """Use the reviewed original's title and score when another match is selected."""

        draft = generate_dmca_draft(
            scan={"top_match": {"protected_title": "Top original", "content_similarity": 0.95}},
            match={"protected_title": "Other original", "content_similarity": 0.72},
            verdict_explanation={"explanation": "The same scene is visible."},
        )

        self.assertIn("Other original", draft["subject"])
        self.assertIn("Similarity score: 0.720", draft["body"])


if __name__ == "__main__":
    unittest.main()
