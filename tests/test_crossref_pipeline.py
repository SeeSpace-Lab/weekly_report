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


if __name__ == "__main__":
    unittest.main()
