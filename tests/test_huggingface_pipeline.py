from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from weekly_intel.collectors.huggingface import HuggingFaceCollector
from weekly_intel.contracts import CollectionWindow, SourceConfig
from weekly_intel.db import Database
from weekly_intel.repository import Repository


class HuggingFacePipelineTest(unittest.TestCase):
    def test_search_deduplicates_and_normalizes_model(self) -> None:
        payload = json.dumps(
            [
                {
                    "id": "orbit-lab/edge-llm-runtime",
                    "author": "orbit-lab",
                    "sha": "abcdef123",
                    "createdAt": "2026-07-20T08:00:00Z",
                    "lastModified": "2026-07-24T08:00:00Z",
                    "downloads": 1000,
                    "likes": 42,
                    "tags": ["llm", "edge", "inference"],
                    "pipeline_tag": "text-generation",
                    "cardData": {
                        "summary": "An edge LLM inference runtime model."
                    },
                }
            ]
        ).encode()
        source = SourceConfig(
            source_id="huggingface_hub",
            name="Hugging Face",
            source_type="model_hub",
            connector="HuggingFaceCollector",
            tier="A_Active",
            options={
                "resource_types": ["models"],
                "search_terms": ["edge llm", "llm inference"],
                "limit_per_query": 5,
            },
        )
        collector = HuggingFaceCollector(
            fetcher=lambda url, headers, timeout: payload
        )
        window = CollectionWindow(
            datetime(2026, 7, 18, tzinfo=timezone.utc),
            datetime(2026, 7, 25, tzinfo=timezone.utc),
        )
        batch = collector.collect(source, window)
        self.assertEqual(batch.status.value, "ok")
        self.assertEqual(len(batch.documents), 1)
        self.assertEqual(batch.stats["fetched"], 2)
        with tempfile.TemporaryDirectory() as temp_dir:
            database = Database(Path(temp_dir) / "test.db")
            database.initialize(
                Path(__file__).parents[1] / "schemas" / "weekly_intel.sql"
            )
            with database.transaction() as connection:
                repository = Repository(connection)
                repository.upsert_source(source)
                repository.start_run(
                    batch.run_id, source, window, None, collector.name
                )
                created, skipped = repository.ingest_documents(
                    batch.run_id, batch.documents
                )
                repository.finish_run(batch, created, skipped)
            with database.session() as connection:
                item = connection.execute(
                    "SELECT item_type, canonical_title FROM research_items"
                ).fetchone()
                claim = connection.execute(
                    "SELECT claim_type, claim_text FROM evidence_claims"
                ).fetchone()
            self.assertEqual(item["item_type"], "framework")
            self.assertEqual(item["canonical_title"], "orbit-lab/edge-llm-runtime")
            self.assertEqual(claim["claim_type"], "release_status")
            self.assertIn("model update", claim["claim_text"])


if __name__ == "__main__":
    unittest.main()
