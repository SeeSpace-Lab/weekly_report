from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from weekly_intel.codex_handoff import CodexWeeklyHandoff
from weekly_intel.db import Database
from weekly_intel.review import ReviewService


class CodexWeeklyHandoffTest(unittest.TestCase):
    def test_exports_shortlist_and_imports_verified_cards(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(__file__).parents[1]
            database = Database(Path(temp_dir) / "weekly.db")
            database.initialize(root / "schemas" / "weekly_intel.sql")
            with database.transaction() as connection:
                for index in (1, 2):
                    connection.execute(
                        """
                        INSERT INTO research_items (
                            item_id, item_type, canonical_title,
                            normalized_title, canonical_url,
                            abstract_or_summary, authors_json,
                            organizations_json, first_published_at,
                            latest_updated_at, language, created_at, updated_at
                        ) VALUES (?, 'paper', ?, ?, ?, ?, '[]', '[]',
                                  ?, ?, 'en', ?, ?)
                        """,
                        (
                            f"item-{index}",
                            f"Paper {index}",
                            f"paper {index}",
                            f"https://example.com/{index}",
                            "A detailed abstract about power-aware LLM inference.",
                            "2026-07-20T00:00:00+00:00",
                            "2026-07-24T00:00:00+00:00",
                            "2026-07-24T00:00:00+00:00",
                            "2026-07-24T00:00:00+00:00",
                        ),
                    )
                    connection.execute(
                        """
                        INSERT INTO department_assessments (
                            assessment_id, department_id, item_id,
                            topic_tags_json, global_importance,
                            department_relevance, novelty, evidence_quality,
                            trend_signal, recommendation,
                            recommended_section, rationale,
                            estimated_read_minutes, model_version,
                            prompt_version, assessed_at
                        ) VALUES (?, 'orbitinfer', ?, '["power_aware"]',
                                  .9, .95, .8, .85, .75, 'must_read',
                                  'power_reliability_edge_distributed',
                                  'Strongly relevant verified candidate',
                                  6, 'rules', 'v1', ?)
                        """,
                        (
                            f"assessment-{index}",
                            f"item-{index}",
                            "2026-07-24T00:00:00+00:00",
                        ),
                    )
                connection.execute(
                    """
                    INSERT INTO weekly_issues (
                        issue_id, department_id, iso_week, window_start,
                        window_end, status, title, summary,
                        target_read_minutes, generated_at
                    ) VALUES (
                        'issue-1', 'orbitinfer', '2026-W30',
                        '2026-07-18T00:00:00+00:00',
                        '2026-07-25T00:00:00+00:00', 'draft',
                        'Test weekly', '- trend', 30,
                        '2026-07-25T00:00:00+00:00'
                    )
                    """
                )

            handoff = CodexWeeklyHandoff(
                root / "config" / "departments" / "orbitinfer.yaml"
            )
            brief_path = Path(temp_dir) / "brief.json"
            with database.session() as connection:
                handoff.export_brief(connection, "issue-1", brief_path)
            brief = json.loads(brief_path.read_text(encoding="utf-8"))
            self.assertEqual(len(brief["candidates"]), 2)

            analysis_path = Path(temp_dir) / "analysis.json"
            analysis_path.write_text(
                json.dumps(
                    {
                        "schemaVersion": 1,
                        "issueId": "issue-1",
                        "selections": [
                            {
                                "itemId": "item-1",
                                "section": (
                                    "power_reliability_edge_distributed"
                                ),
                                "role": "must_read",
                                "readMinutes": 6,
                                "selectionReason": (
                                    "直接研究动态功率预算下的大模型推理调度。"
                                ),
                                "titleZh": "面向动态功率预算的推理调度",
                                "oneSentenceZh": (
                                    "该工作用在线调度器在变化功率预算下协调推理请求。"
                                ),
                                "problemZh": (
                                    "研究动态功率限制下如何维持推理吞吐和延迟目标。"
                                ),
                                "methodZh": (
                                    "方法根据实时功率余量和请求队列状态联合调整批次与执行顺序。"
                                ),
                                "resultZh": (
                                    "摘要报告该方法改善了功率约束下的吞吐稳定性。"
                                ),
                                "contributions": [
                                    "提出功率预算感知的在线推理调度方法。"
                                ],
                                "evidence": [
                                    "论文摘要明确描述动态功率预算与吞吐稳定性。"
                                ],
                                "limitations": [
                                    "候选包只有摘要，具体数值仍需全文复核。"
                                ],
                                "departmentImplication": (
                                    "可用于星载平台功率波动条件下的调度策略设计。"
                                ),
                                "confidence": 0.72,
                            }
                        ],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            with database.transaction() as connection:
                issue_id, count = handoff.import_analysis(
                    connection,
                    analysis_path,
                    Path(temp_dir) / "report.md",
                    Path(temp_dir) / "report-data.json",
                )
            self.assertEqual(issue_id, "issue-1")
            self.assertEqual(count, 1)
            readiness = ReviewService(database).approval_readiness("issue-1")
            self.assertTrue(readiness.ready, readiness.blockers)
            with database.session() as connection:
                card = connection.execute(
                    "SELECT model_version FROM deep_read_cards"
                ).fetchone()
            self.assertEqual(
                card["model_version"], "codex-scheduled-task-v1"
            )


if __name__ == "__main__":
    unittest.main()
