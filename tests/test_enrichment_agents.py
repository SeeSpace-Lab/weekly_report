from __future__ import annotations

import tempfile
import unittest
import uuid
from datetime import datetime, timezone
from pathlib import Path

from weekly_intel.agents.enrichment import (
    InterpretationLinkAgent,
    VersionDiffAgent,
)
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
from weekly_intel.utils import sha256_text


class EnrichmentAgentsTest(unittest.TestCase):
    def test_version_diff_and_interpretation_link(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(__file__).parents[1]
            database = Database(Path(temp_dir) / "test.db")
            database.initialize(root / "schemas" / "weekly_intel.sql")
            now = datetime(2026, 7, 24, tzinfo=timezone.utc)
            source = SourceConfig(
                source_id="manual_inbox",
                name="Manual",
                source_type="manual",
                connector="ManualInboxCollector",
                tier="Manual",
            )
            documents = [
                CollectedDocument(
                    source_id=source.source_id,
                    external_id="paper-v1",
                    document_type=DocumentType.PAPER_RECORD,
                    canonical_url="https://arxiv.org/abs/2607.12345",
                    title="KV Cache Scheduling",
                    published_at=now,
                    updated_at_source=now,
                    discovered_at=now,
                    summary="A short scheduling method.",
                    identifiers={"arxiv": "2607.12345"},
                    metadata={"version": "v1"},
                    content_hash=sha256_text("paper-v1"),
                ),
                CollectedDocument(
                    source_id=source.source_id,
                    external_id="paper-v2",
                    document_type=DocumentType.PAPER_RECORD,
                    canonical_url="https://arxiv.org/abs/2607.12345",
                    title="KV Cache Scheduling",
                    published_at=now,
                    updated_at_source=now,
                    discovered_at=now,
                    summary="A substantially extended scheduling method with power-aware evaluation.",
                    identifiers={"arxiv": "2607.12345"},
                    metadata={"version": "v2"},
                    content_hash=sha256_text("paper-v2"),
                ),
                CollectedDocument(
                    source_id=source.source_id,
                    external_id="review-1",
                    document_type=DocumentType.REVIEW_ARTICLE,
                    canonical_url="https://mp.weixin.qq.com/s/review",
                    title="KV Cache调度论文解读",
                    published_at=now,
                    discovered_at=now,
                    summary="这篇文章解读KV Cache调度与动态功耗预算。",
                    identifiers={"url_fingerprint": sha256_text("review-url")},
                    metadata={
                        "item_title": "KV Cache调度论文解读",
                        "related_arxiv_ids": ["2607.12345"],
                    },
                    content_hash=sha256_text("review-1"),
                ),
            ]
            batch = CollectionBatch(
                run_id=str(uuid.uuid4()),
                source_id=source.source_id,
                status=BatchStatus.OK,
                documents=documents,
            )
            window = CollectionWindow(now, now)
            with database.transaction() as connection:
                repository = Repository(connection)
                repository.upsert_source(source)
                repository.start_run(
                    batch.run_id, source, window, None, "ManualInboxCollector"
                )
                created, skipped = repository.ingest_documents(
                    batch.run_id, documents
                )
                repository.finish_run(batch, created, skipped)
                diff_count = VersionDiffAgent().run(connection)
                claims, links = InterpretationLinkAgent().run(connection)
            self.assertEqual(diff_count, 1)
            self.assertEqual(claims, 1)
            self.assertEqual(links, 1)
            with database.session() as connection:
                significance = connection.execute(
                    """
                    SELECT change_significance FROM item_versions
                    WHERE version_label='v2'
                    """
                ).fetchone()[0]
                relation = connection.execute(
                    "SELECT relation_type FROM item_relations"
                ).fetchone()[0]
            self.assertIn(significance, {"material", "major"})
            self.assertEqual(relation, "interprets")


if __name__ == "__main__":
    unittest.main()
