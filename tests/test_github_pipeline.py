from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from weekly_intel.collectors.github import GitHubCollector
from weekly_intel.contracts import CollectionWindow, SourceConfig
from weekly_intel.db import Database
from weekly_intel.repository import Repository


def github_source() -> SourceConfig:
    return SourceConfig(
        source_id="github_vllm",
        name="vLLM GitHub",
        source_type="repository",
        connector="GitHubCollector",
        tier="S_Core",
        options={"repository": "vllm-project/vllm"},
    )


def releases_payload() -> bytes:
    return json.dumps(
        [
            {
                "id": 101,
                "tag_name": "v0.12.0",
                "name": "vLLM v0.12.0",
                "body": "Adds KV cache offloading and scheduling improvements.",
                "html_url": "https://github.com/vllm-project/vllm/releases/tag/v0.12.0",
                "published_at": "2026-07-22T10:00:00Z",
                "updated_at": "2026-07-23T10:00:00Z",
                "author": {"login": "maintainer"},
                "assets": [],
                "prerelease": False,
                "draft": False,
            }
        ]
    ).encode()


class GitHubPipelineTest(unittest.TestCase):
    def test_release_is_normalized_as_framework_version(self) -> None:
        window = CollectionWindow(
            datetime(2026, 7, 18, tzinfo=timezone.utc),
            datetime(2026, 7, 25, tzinfo=timezone.utc),
        )
        collector = GitHubCollector(
            fetcher=lambda url, headers, timeout: releases_payload()
        )
        batch = collector.collect(github_source(), window)
        self.assertEqual(batch.status.value, "ok")
        self.assertEqual(batch.documents[0].metadata["version"], "v0.12.0")
        with tempfile.TemporaryDirectory() as temp_dir:
            database = Database(Path(temp_dir) / "test.db")
            database.initialize(
                Path(__file__).parents[1] / "schemas" / "weekly_intel.sql"
            )
            with database.transaction() as connection:
                repository = Repository(connection)
                repository.upsert_source(github_source())
                repository.start_run(
                    batch.run_id,
                    github_source(),
                    window,
                    None,
                    collector.name,
                )
                created, skipped = repository.ingest_documents(
                    batch.run_id, batch.documents
                )
                repository.finish_run(batch, created, skipped)
            with database.session() as connection:
                item = connection.execute(
                    "SELECT item_type, canonical_title FROM research_items"
                ).fetchone()
                version = connection.execute(
                    "SELECT version_kind, version_label FROM item_versions"
                ).fetchone()
                claim = connection.execute(
                    "SELECT claim_type FROM evidence_claims"
                ).fetchone()
            self.assertEqual(item["item_type"], "framework")
            self.assertEqual(item["canonical_title"], "vllm-project/vllm")
            self.assertEqual(version["version_kind"], "release")
            self.assertEqual(version["version_label"], "v0.12.0")
            self.assertEqual(claim["claim_type"], "release_status")


if __name__ == "__main__":
    unittest.main()
