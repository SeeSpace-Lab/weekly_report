from __future__ import annotations

import sqlite3
import unittest

from weekly_intel.paper_content import PaperContentWorker


class PaperContentWorkerTest(unittest.TestCase):
    def test_fetches_selected_arxiv_html_and_caches_it(self) -> None:
        connection = sqlite3.connect(":memory:")
        connection.row_factory = sqlite3.Row
        connection.executescript(
            """
            CREATE TABLE research_items (
                item_id TEXT PRIMARY KEY, item_type TEXT NOT NULL
            );
            CREATE TABLE item_identifiers (
                item_id TEXT, scheme TEXT, value TEXT
            );
            CREATE TABLE weekly_selections (
                issue_id TEXT, item_id TEXT, content_role TEXT, position INTEGER
            );
            CREATE TABLE paper_contents (
                content_id TEXT PRIMARY KEY, item_id TEXT, source_url TEXT,
                content_type TEXT, content_text TEXT, content_hash TEXT,
                fetched_at TEXT, parser_version TEXT,
                UNIQUE (item_id, source_url, content_hash)
            );
            INSERT INTO research_items VALUES ('paper-1', 'paper');
            INSERT INTO item_identifiers VALUES
                ('paper-1', 'arxiv', '2607.12345v2');
            INSERT INTO weekly_selections VALUES
                ('issue-1', 'paper-1', 'must_read', 1);
            """
        )
        html = (
            "<html><body><article><h1>Power-Aware Inference</h1>"
            + "".join(
                f"<p>Section {index}: adaptive scheduling evidence.</p>"
                for index in range(40)
            )
            + "</article></body></html>"
        ).encode()
        urls: list[str] = []

        def fetcher(url: str, headers: dict[str, str], timeout: float) -> bytes:
            urls.append(url)
            return html

        worker = PaperContentWorker(fetcher=fetcher)
        first = worker.run(connection, "issue-1")
        second = worker.run(connection, "issue-1")

        self.assertEqual(first.fetched, 1)
        self.assertEqual(second.cached, 1)
        self.assertEqual(urls, ["https://arxiv.org/html/2607.12345"])
        text = connection.execute(
            "SELECT content_text FROM paper_contents"
        ).fetchone()["content_text"]
        self.assertIn("adaptive scheduling evidence", text)


if __name__ == "__main__":
    unittest.main()
