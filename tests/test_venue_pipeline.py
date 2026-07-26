from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from weekly_intel.collectors.venue import VenueCollector
from weekly_intel.contracts import CollectionWindow, SourceConfig
from weekly_intel.db import Database
from weekly_intel.repository import Repository


HTML = b"""<!doctype html>
<html><head>
<title>OSDI '27</title>
<meta name="description" content="Official call for papers and important dates">
</head><body>
<h1>OSDI '27 Call for Papers</h1>
<p>Abstract registrations due December 1, 2026.</p>
<script>dynamicNoise()</script>
</body></html>"""


class VenuePipelineTest(unittest.TestCase):
    def test_official_page_snapshot(self) -> None:
        source = SourceConfig(
            source_id="venue_official_pages",
            name="Venue pages",
            source_type="venue",
            connector="VenueCollector",
            tier="S_Core",
            options={
                "pages": [
                    {
                        "id": "osdi-2027",
                        "name": "OSDI 2027",
                        "category": "systems",
                        "url": "https://www.usenix.org/conference/osdi27",
                    }
                ]
            },
        )
        collector = VenueCollector(
            fetcher=lambda url, headers, timeout: HTML
        )
        window = CollectionWindow(
            datetime(2026, 7, 20, tzinfo=timezone.utc),
            datetime(2026, 7, 26, tzinfo=timezone.utc),
        )
        batch = collector.collect(source, window)
        self.assertEqual(batch.status.value, "ok")
        self.assertEqual(batch.documents[0].title, "OSDI '27")
        self.assertNotIn("dynamicNoise", batch.documents[0].content_text)
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
            self.assertEqual(item["item_type"], "venue_event")
            self.assertEqual(item["canonical_title"], "OSDI 2027")


if __name__ == "__main__":
    unittest.main()
