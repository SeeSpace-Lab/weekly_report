from __future__ import annotations

import sqlite3
import tempfile
import unittest
import urllib.error
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

from weekly_intel.collectors.arxiv import ArxivCollector
from weekly_intel.contracts import CollectionWindow, SourceConfig
from weekly_intel.db import Database
from weekly_intel.repository import Repository


ATOM_TEMPLATE = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom"
      xmlns:arxiv="http://arxiv.org/schemas/atom">
  <entry>
    <id>http://arxiv.org/abs/2607.12345v{version}</id>
    <updated>{updated}</updated>
    <published>2026-07-20T08:00:00Z</published>
    <title>Power-Aware Scheduling for LLM Inference</title>
    <summary>A runtime for dynamic power budgets and KV cache placement.</summary>
    <author><name>Alice Example</name></author>
    <author><name>Bob Example</name></author>
    <category term="cs.DC"/>
    <arxiv:primary_category term="cs.DC"/>
    <link title="pdf" href="https://arxiv.org/pdf/2607.12345"/>
  </entry>
</feed>
"""

OAI_PAYLOAD = b"""<?xml version="1.0" encoding="UTF-8"?>
<OAI-PMH xmlns="http://www.openarchives.org/OAI/2.0/">
  <ListRecords>
    <record>
      <header><identifier>oai:arXiv.org:2607.54321</identifier></header>
      <metadata>
        <arXiv xmlns="http://arxiv.org/OAI/arXiv/">
          <id>2607.54321</id><created>2026-07-24</created>
          <authors><author><keyname>Example</keyname><forenames>Alice</forenames></author></authors>
          <title>Efficient LLM Inference Runtime</title>
          <categories>cs.DC cs.LG</categories>
          <abstract>KV cache scheduling for language model serving.</abstract>
        </arXiv>
      </metadata>
    </record>
    <resumptionToken></resumptionToken>
  </ListRecords>
</OAI-PMH>"""


def source() -> SourceConfig:
    return SourceConfig(
        source_id="arxiv",
        name="arXiv",
        source_type="paper_api",
        connector="ArxivCollector",
        tier="S_Core",
        options={"categories": ["cs.DC"], "max_results": 10},
    )


class ArxivPipelineTest(unittest.TestCase):
    def setUp(self) -> None:
        self.window = CollectionWindow(
            datetime(2026, 7, 18, tzinfo=timezone.utc),
            datetime(2026, 7, 25, tzinfo=timezone.utc),
        )

    def test_parse_atom_entry(self) -> None:
        payload = ATOM_TEMPLATE.format(
            version=2, updated="2026-07-24T09:30:00Z"
        ).encode()
        batch = ArxivCollector().parse(
            payload, source(), self.window, "run-parse"
        )
        self.assertEqual(batch.status.value, "ok")
        self.assertEqual(len(batch.documents), 1)
        document = batch.documents[0]
        self.assertEqual(document.identifiers["arxiv"], "2607.12345")
        self.assertEqual(document.metadata["version"], "v2")
        self.assertIn("dynamic power budgets", document.summary)

    def test_query_contains_categories_and_terms(self) -> None:
        configured = replace(
            source(), options={
                "categories": ["cs.DC", "cs.LG"],
                "search_terms": ["LLM inference", "KV cache"],
            }
        )
        url = ArxivCollector().build_url(configured, self.window)
        self.assertIn("search_query=", url)
        self.assertIn("LLM+inference", url)
        self.assertIn("cat%3Acs.DC", url)

    def test_rate_limit_is_retried(self) -> None:
        attempts = 0
        sleeps: list[float] = []

        def fetch(url, headers, timeout):
            nonlocal attempts
            attempts += 1
            if attempts == 1:
                raise urllib.error.HTTPError(
                    url, 429, "Too Many Requests", {"Retry-After": "0"}, None
                )
            return ATOM_TEMPLATE.format(
                version=2, updated="2026-07-24T09:30:00Z"
            ).encode()

        batch = ArxivCollector(fetcher=fetch, sleeper=sleeps.append).collect(
            replace(source(), options={**source().options, "max_retries": 2}),
            self.window,
        )
        self.assertEqual(batch.status.value, "ok")
        self.assertEqual(attempts, 2)
        self.assertEqual(sleeps, [0.0])

    def test_oai_fallback_is_used_after_api_rate_limit(self) -> None:
        requested: list[str] = []

        def fetch(url, headers, timeout):
            requested.append(url)
            if "/api/query" in url:
                raise urllib.error.HTTPError(
                    url, 429, "Too Many Requests", {}, None
                )
            return OAI_PAYLOAD

        configured = replace(
            source(),
            options={
                **source().options,
                "search_terms": ["LLM inference"],
                "oai_fallback": True,
                "max_retries": 0,
            },
        )
        batch = ArxivCollector(fetcher=fetch).collect(configured, self.window)
        self.assertEqual(batch.status.value, "ok")
        self.assertEqual(batch.stats["provider_mode"], "oai_fallback")
        self.assertEqual(batch.documents[0].identifiers["arxiv"], "2607.54321")
        self.assertEqual(len(requested), 2)

    def test_versions_and_idempotency(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db = Database(Path(temp_dir) / "test.db")
            schema = Path(__file__).parents[1] / "schemas" / "weekly_intel.sql"
            db.initialize(schema)
            collector = ArxivCollector()

            for version, updated, run_id in [
                (1, "2026-07-21T09:30:00Z", "run-v1"),
                (2, "2026-07-24T09:30:00Z", "run-v2"),
                (2, "2026-07-24T09:30:00Z", "run-v2-repeat"),
            ]:
                payload = ATOM_TEMPLATE.format(
                    version=version, updated=updated
                ).encode()
                batch = collector.parse(payload, source(), self.window, run_id)
                with db.transaction() as connection:
                    repository = Repository(connection)
                    repository.upsert_source(source())
                    repository.start_run(
                        run_id, source(), self.window, None, collector.name
                    )
                    created, skipped = repository.ingest_documents(
                        run_id, batch.documents
                    )
                    batch = replace(batch, run_id=run_id)
                    repository.finish_run(batch, created, skipped)

            connection = db.connect()
            try:
                raw_count = connection.execute(
                    "SELECT COUNT(*) FROM raw_documents"
                ).fetchone()[0]
                item_count = connection.execute(
                    "SELECT COUNT(*) FROM research_items"
                ).fetchone()[0]
                version_count = connection.execute(
                    "SELECT COUNT(*) FROM item_versions"
                ).fetchone()[0]
            finally:
                connection.close()
            self.assertEqual(raw_count, 2)
            self.assertEqual(item_count, 1)
            self.assertEqual(version_count, 2)


if __name__ == "__main__":
    unittest.main()
