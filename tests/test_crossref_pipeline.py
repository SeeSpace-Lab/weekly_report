from __future__ import annotations

import json
import unittest
from datetime import datetime, timezone

from weekly_intel.collectors.crossref import CrossrefCollector
from weekly_intel.contracts import CollectionWindow, SourceConfig


class CrossrefPipelineTest(unittest.TestCase):
    def test_doi_records_are_deduplicated_across_queries(self) -> None:
        record = {
            "DOI": "10.1000/OrbitInfer.1",
            "title": ["Power-Aware LLM Inference"],
            "author": [{"given": "Ada", "family": "Lovelace"}],
            "URL": "https://doi.org/10.1000/OrbitInfer.1",
            "published": {"date-parts": [[2026, 7, 22]]},
            "indexed": {"date-time": "2026-07-24T12:00:00Z"},
            "container-title": ["MLSys"],
            "type": "proceedings-article",
        }

        def fetcher(url: str, headers: dict[str, str], timeout: float) -> bytes:
            self.assertIn("query.bibliographic=", url)
            return json.dumps({"message": {"items": [record]}}).encode()

        source = SourceConfig(
            source_id="crossref",
            name="Crossref",
            source_type="paper_api",
            connector="CrossrefCollector",
            tier="A_Active",
            options={
                "search_terms": ["LLM inference", "power aware"],
                "rows_per_query": 10,
            },
        )
        window = CollectionWindow(
            datetime(2026, 7, 20, tzinfo=timezone.utc),
            datetime(2026, 7, 25, tzinfo=timezone.utc),
        )
        batch = CrossrefCollector(fetcher).collect(source, window)

        self.assertEqual(batch.status.value, "ok")
        self.assertEqual(len(batch.documents), 1)
        self.assertEqual(
            batch.documents[0].identifiers["doi"],
            "10.1000/orbitinfer.1",
        )
        self.assertEqual(batch.documents[0].metadata["venue"], "MLSys")
        self.assertEqual(batch.stats["fetched"], 2)

    def test_cursor_pagination_reaches_records_before_local_week_end(self) -> None:
        outside = {
            "DOI": "10.1000/outside",
            "title": ["Indexed after the local week ended"],
            "indexed": {"date-time": "2026-08-02T23:59:00Z"},
            "published": {"date-parts": [[2026, 8, 2]]},
        }
        inside = {
            "DOI": "10.1000/inside",
            "title": ["Satellite Computing in LEO"],
            "indexed": {"date-time": "2026-08-02T12:00:00Z"},
            "published": {"date-parts": [[2026, 8, 2]]},
        }
        calls = 0

        def fetcher(url: str, headers: dict[str, str], timeout: float) -> bytes:
            nonlocal calls
            calls += 1
            message = (
                {"items": [outside], "next-cursor": "page-2"}
                if calls == 1
                else {"items": [inside]}
            )
            return json.dumps({"message": message}).encode()

        source = SourceConfig(
            source_id="crossref",
            name="Crossref",
            source_type="paper_api",
            connector="CrossrefCollector",
            tier="A_Active",
            options={
                "search_terms": ["satellite computing"],
                "rows_per_query": 1,
                "max_pages": 2,
            },
        )
        window = CollectionWindow(
            datetime(2026, 7, 26, 16, tzinfo=timezone.utc),
            datetime(2026, 8, 2, 15, 59, tzinfo=timezone.utc),
        )
        batch = CrossrefCollector(fetcher).collect(source, window)

        self.assertEqual(calls, 2)
        self.assertEqual(len(batch.documents), 1)
        self.assertEqual(
            batch.documents[0].identifiers["doi"],
            "10.1000/inside",
        )


if __name__ == "__main__":
    unittest.main()
