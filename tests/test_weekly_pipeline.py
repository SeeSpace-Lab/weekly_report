from __future__ import annotations

import tempfile
import unittest
import uuid
import json
from datetime import datetime, timezone
from pathlib import Path

from weekly_intel.config import load_yaml
from weekly_intel.contracts import (
    BatchStatus,
    CollectionBatch,
    CollectionWindow,
    CollectedDocument,
    DocumentType,
    SourceConfig,
)
from weekly_intel.db import Database
from weekly_intel.repository import Repository
from weekly_intel.review import ReviewService
from weekly_intel.utils import json_dumps, sha256_text
from weekly_intel.weekly import WeeklyPipelineService
from weekly_intel.site_export import SiteDataExportAgent


class WeeklyPipelineTest(unittest.TestCase):
    def test_assess_select_and_render(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(__file__).parents[1]
            database = Database(Path(temp_dir) / "weekly.db")
            database.initialize(root / "schemas" / "weekly_intel.sql")
            source = SourceConfig(
                source_id="arxiv",
                name="arXiv",
                source_type="paper_api",
                connector="ArxivCollector",
                tier="S_Core",
            )
            start = datetime(2026, 7, 18, tzinfo=timezone.utc)
            end = datetime(2026, 7, 25, tzinfo=timezone.utc)
            documents = []
            for index, (title, summary) in enumerate(
                [
                    (
                        "Power-Aware Scheduling for LLM Inference",
                        "Dynamic power budgets, thermal limits and inference scheduling.",
                    ),
                    (
                        "Hierarchical KV Cache for Disaggregated LLM Serving",
                        "CXL memory and KV cache offloading for low latency serving.",
                    ),
                    (
                        "Expert Placement for Efficient MoE Inference",
                        "Mixture of experts placement and expert prefetch.",
                    ),
                    (
                        "Fault-Tolerant Edge LLM Runtime",
                        "Recovery from soft errors in real-time on-device inference.",
                    ),
                ],
                start=1,
            ):
                version = "v2" if index <= 3 else "v1"
                payload = {
                    "title": title,
                    "summary": summary,
                    "version": version,
                }
                documents.append(
                    CollectedDocument(
                        source_id="arxiv",
                        external_id=f"2607.1000{index}v1",
                        document_type=DocumentType.PAPER_RECORD,
                        canonical_url=f"https://arxiv.org/abs/2607.1000{index}",
                        title=title,
                        published_at=start,
                        updated_at_source=end,
                        discovered_at=end,
                        authors=("Researcher A",),
                        summary=summary,
                        identifiers={"arxiv": f"2607.1000{index}"},
                        metadata={"version": version, "categories": ["cs.DC"]},
                        raw_payload=payload,
                        content_hash=sha256_text(json_dumps(payload)),
                    )
                )
            batch = CollectionBatch(
                run_id=str(uuid.uuid4()),
                source_id="arxiv",
                status=BatchStatus.OK,
                documents=documents,
            )
            window = CollectionWindow(start, end)
            with database.transaction() as connection:
                repository = Repository(connection)
                repository.upsert_source(source)
                repository.start_run(
                    batch.run_id, source, window, None, "ArxivCollector"
                )
                created, skipped = repository.ingest_documents(
                    batch.run_id, batch.documents
                )
                repository.finish_run(batch, created, skipped)

            department = load_yaml(
                root / "config" / "departments" / "orbitinfer.yaml"
            )
            output = Path(temp_dir) / "report.md"
            result = WeeklyPipelineService(database, department).build(
                "2026-W30", start, end, output
            )
            content = output.read_text(encoding="utf-8")
            self.assertEqual(result.assessed_count, 4)
            self.assertGreaterEqual(result.selection_count, 3)
            self.assertGreaterEqual(result.deep_reads, 3)
            self.assertLessEqual(result.estimated_read_minutes, 30)
            self.assertIn("# 星载大模型推理引擎周报", content)
            self.assertIn("## 本周趋势", content)
            self.assertIn("Power-Aware Scheduling", content)
            self.assertIn("一句话读懂", content)
            self.assertIn("研究问题", content)
            self.assertIn("主要贡献", content)
            with database.session() as connection:
                issue = connection.execute(
                    "SELECT status, output_markdown_url FROM weekly_issues"
                ).fetchone()
                assessments = connection.execute(
                    "SELECT COUNT(*) FROM department_assessments"
                ).fetchone()[0]
                deep_read_cards = connection.execute(
                    "SELECT COUNT(*) FROM deep_read_cards"
                ).fetchone()[0]
            self.assertEqual(issue["status"], "draft")
            self.assertEqual(assessments, 4)
            self.assertGreaterEqual(deep_read_cards, 3)
            self.assertEqual(Path(issue["output_markdown_url"]), output.resolve())
            site_data = Path(temp_dir) / "report-data.json"
            with database.transaction() as connection:
                SiteDataExportAgent().export(
                    connection, result.issue_id, site_data
                )
            payload = json.loads(site_data.read_text(encoding="utf-8"))
            library_payload = json.loads(
                site_data.with_name("library-data.json").read_text(
                    encoding="utf-8"
                )
            )
            source_payload = json.loads(
                site_data.with_name("source-data.json").read_text(
                    encoding="utf-8"
                )
            )
            archive_payload = json.loads(
                site_data.with_name("archive-data.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertGreaterEqual(len(library_payload["papers"]), 8)
            self.assertGreaterEqual(len(library_payload["venues"]), 20)
            self.assertEqual(source_payload["accounts"], [])
            self.assertEqual(
                archive_payload["issues"][0]["issue"]["isoWeek"],
                "2026-W30",
            )
            deep_reads = [
                item["deepRead"]
                for section in payload["sections"]
                for item in section["items"]
                if item["deepRead"]
            ]
            self.assertGreaterEqual(len(deep_reads), 3)
            self.assertIn("问题", deep_reads[0]["problemZh"])

            review_service = ReviewService(database)
            with database.session() as connection:
                selections = connection.execute(
                    """
                    SELECT s.selection_id, r.canonical_title
                    FROM weekly_selections s
                    JOIN research_items r ON r.item_id=s.item_id
                    WHERE s.issue_id=? ORDER BY s.position
                    """,
                    (result.issue_id,),
                ).fetchall()
            rejected_title = selections[0]["canonical_title"]
            for index, selection in enumerate(selections):
                review_service.review_selection(
                    selection["selection_id"],
                    reviewer="test-reviewer",
                    decision="reject" if index == 0 else "approve",
                )
            reviewed_content = output.read_text(encoding="utf-8")
            self.assertNotIn(rejected_title, reviewed_content)
            review_service.approve_issue(result.issue_id)
            review_service.publish_issue(
                result.issue_id, "https://example.test/2026-W30"
            )
            with database.session() as connection:
                published = connection.execute(
                    """
                    SELECT status, output_page_url FROM weekly_issues
                    WHERE issue_id=?
                    """,
                    (result.issue_id,),
                ).fetchone()
            self.assertEqual(published["status"], "published")
            self.assertEqual(
                published["output_page_url"],
                "https://example.test/2026-W30",
            )


if __name__ == "__main__":
    unittest.main()
