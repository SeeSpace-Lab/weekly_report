from __future__ import annotations

import sqlite3
import unittest

from weekly_intel.agents.assessment import DepartmentAssessmentAgent


class StrongNewPreprintPolicyTest(unittest.TestCase):
    @staticmethod
    def _row() -> sqlite3.Row:
        connection = sqlite3.connect(":memory:")
        connection.row_factory = sqlite3.Row
        return connection.execute(
            """
            SELECT
                'paper-1' AS item_id,
                'Visual Token Compression for Vision Language Models'
                    AS canonical_title,
                'A visual token compression method for a multimodal model.'
                    AS abstract_or_summary,
                '' AS metadata_text,
                '' AS publication_status,
                '' AS release_status,
                'paper' AS item_type,
                'S_Core' AS source_tier,
                1 AS version_count,
                1 AS max_version_number,
                1 AS identifier_count
            """
        ).fetchone()

    @staticmethod
    def _department(allow: bool) -> dict:
        return {
            "department_id": "model_and_application",
            "core_topics": [
                {
                    "id": "token_compression",
                    "weight": 1.0,
                    "section": "primary_topic",
                    "keywords": [
                        "visual token compression",
                        "token compression",
                        "vision language model",
                    ],
                }
            ],
            "keywords": {"include": ["vision language model"]},
            "source_pool": {"papers": ["arxiv"]},
            "candidate_policy": {
                "allow_strong_new_preprints": allow,
                "min_strong_new_preprint_relevance": 0.65,
                "read_minutes": {"strong_new_preprint": 3.0},
            },
        }

    def test_high_relevance_v1_preprint_can_be_recommended(self) -> None:
        result = DepartmentAssessmentAgent(
            self._department(True)
        ).assess_row(self._row())
        self.assertEqual(result.recommendation, "recommended")
        self.assertEqual(result.estimated_read_minutes, 3.0)
        self.assertIn("高相关新预印本", result.rationale)

    def test_v1_preprint_remains_archived_without_opt_in(self) -> None:
        result = DepartmentAssessmentAgent(
            self._department(False)
        ).assess_row(self._row())
        self.assertEqual(result.recommendation, "archive")


if __name__ == "__main__":
    unittest.main()
