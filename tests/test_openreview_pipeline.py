from __future__ import annotations

import json
import tempfile
import unittest
import urllib.parse
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

from weekly_intel.collectors.arxiv import ArxivCollector
from weekly_intel.collectors.openreview import (
    OpenReviewBlockedError,
    OpenReviewCollector,
)
from weekly_intel.candidates import rank_candidates
from weekly_intel.contracts import CollectionWindow, SourceConfig
from weekly_intel.db import Database
from weekly_intel.repository import Repository

from test_arxiv_pipeline import ATOM_TEMPLATE, source as arxiv_source


def openreview_source() -> SourceConfig:
    return SourceConfig(
        source_id="openreview",
        name="OpenReview",
        source_type="paper_api",
        connector="OpenReviewCollector",
        tier="S_Core",
        options={
            "api_v2": "https://api2.openreview.net",
            "venues": [
                {"venue_id": "MLSys.org/2026/Conference", "venue": "MLSys"}
            ],
            "page_size": 100,
            "max_pages": 1,
        },
    )


def note_payload() -> bytes:
    modified = int(
        datetime(2026, 7, 24, 9, 30, tzinfo=timezone.utc).timestamp() * 1000
    )
    created = int(
        datetime(2026, 7, 20, 8, 0, tzinfo=timezone.utc).timestamp() * 1000
    )
    return json.dumps(
        {
            "count": 1,
            "notes": [
                {
                    "id": "openreview-note-1",
                    "forum": "openreview-forum-1",
                    "cdate": created,
                    "mdate": modified,
                    "tcdate": created,
                    "tmdate": modified,
                    "invitation": "MLSys.org/2026/Conference/-/Submission",
                    "content": {
                        "title": {
                            "value": "Power-Aware Scheduling for LLM Inference"
                        },
                        "authors": {
                            "value": ["Alice Example", "Bob Example"]
                        },
                        "abstract": {
                            "value": "Dynamic power budgets for inference."
                        },
                        "venue": {"value": "MLSys 2026 Oral"},
                        "venueid": {
                            "value": "MLSys.org/2026/Conference"
                        },
                        "keywords": {
                            "value": ["LLM serving", "power-aware scheduling"]
                        },
                        "pdf": {"value": "/pdf?id=openreview-forum-1"},
                    },
                }
            ],
        }
    ).encode()


class OpenReviewPipelineTest(unittest.TestCase):
    def setUp(self) -> None:
        self.window = CollectionWindow(
            datetime(2026, 7, 18, tzinfo=timezone.utc),
            datetime(2026, 7, 25, tzinfo=timezone.utc),
        )

    def test_api2_value_fields_are_parsed(self) -> None:
        requested_urls: list[str] = []

        def fetch(url: str, headers: dict[str, str], timeout: float) -> bytes:
            requested_urls.append(url)
            return note_payload()

        collector = OpenReviewCollector(
            fetcher=fetch
        )
        batch = collector.collect(openreview_source(), self.window)
        self.assertEqual(batch.status.value, "ok")
        self.assertEqual(len(batch.documents), 1)
        document = batch.documents[0]
        self.assertEqual(document.metadata["venue_status"], "MLSys 2026 Oral")
        self.assertEqual(
            document.identifiers["openreview_forum"], "openreview-forum-1"
        )
        query = urllib.parse.parse_qs(
            urllib.parse.urlparse(requested_urls[0]).query
        )
        self.assertEqual(query["sort"], ["tmdate:desc"])
        self.assertEqual(
            query["mintmdate"],
            [str(int(self.window.start.timestamp() * 1000))],
        )

    def test_challenge_is_reported_as_blocked(self) -> None:
        def blocked(url: str, headers: dict[str, str], timeout: float) -> bytes:
            raise OpenReviewBlockedError(
                "Challenge verification required",
                "https://openreview.net/challenge",
            )

        batch = OpenReviewCollector(fetcher=blocked).collect(
            openreview_source(), self.window
        )
        self.assertEqual(batch.status.value, "blocked")
        self.assertEqual(batch.errors[0].code, "challenge_required")

    def test_challenge_is_isolated_to_one_venue(self) -> None:
        configured = replace(
            openreview_source(),
            options={
                **openreview_source().options,
                "venues": [
                    {"venue_id": "ICLR.cc/2026/Conference"},
                    {"venue_id": "MLSys.org/2026/Conference"},
                ],
            },
        )

        def fetch(url: str, headers: dict[str, str], timeout: float) -> bytes:
            if "ICLR.cc" in urllib.parse.unquote(url):
                raise OpenReviewBlockedError("Challenge required")
            return note_payload()

        batch = OpenReviewCollector(fetcher=fetch).collect(
            configured, self.window
        )
        self.assertEqual(batch.status.value, "partial")
        self.assertEqual(len(batch.documents), 1)
        self.assertEqual(batch.stats["blocked_venues"], 1)
        self.assertEqual(batch.errors[0].details["venue_id"], "ICLR.cc/2026/Conference")

    def test_openreview_merges_with_arxiv_title_and_adds_status(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            database = Database(Path(temp_dir) / "test.db")
            schema = Path(__file__).parents[1] / "schemas" / "weekly_intel.sql"
            database.initialize(schema)
            arxiv_batch = ArxivCollector().parse(
                ATOM_TEMPLATE.format(
                    version=1, updated="2026-07-21T09:30:00Z"
                ).encode(),
                arxiv_source(),
                self.window,
                "run-arxiv",
            )
            openreview_batch = OpenReviewCollector(
                fetcher=lambda url, headers, timeout: note_payload()
            ).collect(openreview_source(), self.window)
            openreview_batch = replace(
                openreview_batch, run_id="run-openreview"
            )
            for batch, source, collector_name in [
                (arxiv_batch, arxiv_source(), "ArxivCollector"),
                (
                    openreview_batch,
                    openreview_source(),
                    "OpenReviewCollector",
                ),
            ]:
                with database.transaction() as connection:
                    repository = Repository(connection)
                    repository.upsert_source(source)
                    repository.start_run(
                        batch.run_id,
                        source,
                        self.window,
                        None,
                        collector_name,
                    )
                    created, skipped = repository.ingest_documents(
                        batch.run_id, batch.documents
                    )
                    repository.finish_run(batch, created, skipped)

            with database.session() as connection:
                item_count = connection.execute(
                    "SELECT COUNT(*) FROM research_items"
                ).fetchone()[0]
                identifier_count = connection.execute(
                    "SELECT COUNT(*) FROM item_identifiers"
                ).fetchone()[0]
                version_count = connection.execute(
                    "SELECT COUNT(*) FROM item_versions"
                ).fetchone()[0]
                claim_count = connection.execute(
                    "SELECT COUNT(*) FROM evidence_claims"
                ).fetchone()[0]
                candidates = rank_candidates(
                    connection,
                    {
                        "keywords": {
                            "include": ["LLM inference", "power-aware"]
                        }
                    },
                )
            self.assertEqual(item_count, 1)
            self.assertEqual(identifier_count, 2)
            self.assertEqual(version_count, 2)
            self.assertEqual(claim_count, 1)
            self.assertTrue(candidates[0]["accepted_venue_boost"])
            self.assertIn("MLSys 2026 Oral", candidates[0]["publication_status"])


if __name__ == "__main__":
    unittest.main()
