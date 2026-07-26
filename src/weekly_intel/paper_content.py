from __future__ import annotations

import html
import re
import sqlite3
import urllib.request
import uuid
from dataclasses import dataclass
from html.parser import HTMLParser
from typing import Callable

from .utils import isoformat, sha256_text, utc_now


class _ArticleTextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._ignored_depth = 0
        self._chunks: list[str] = []

    def handle_starttag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        if tag in {"script", "style", "nav", "footer", "svg"}:
            self._ignored_depth += 1
        elif not self._ignored_depth and tag in {
            "p",
            "h1",
            "h2",
            "h3",
            "h4",
            "li",
            "figcaption",
        }:
            self._chunks.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "nav", "footer", "svg"}:
            self._ignored_depth = max(0, self._ignored_depth - 1)
        elif not self._ignored_depth and tag in {"p", "li", "section"}:
            self._chunks.append("\n")

    def handle_data(self, data: str) -> None:
        if not self._ignored_depth and data.strip():
            self._chunks.append(data)

    def text(self) -> str:
        lines = (
            " ".join(html.unescape(line).split())
            for line in "".join(self._chunks).splitlines()
        )
        return "\n".join(line for line in lines if line)


@dataclass(frozen=True, slots=True)
class PaperContentRun:
    requested: int
    fetched: int
    cached: int
    failed: int


class PaperContentWorker:
    """Fetch readable arXiv HTML for selected papers before deep analysis."""

    name = "PaperContentWorker"
    parser_version = "arxiv-html-v1"

    def __init__(
        self,
        fetcher: Callable[[str, dict[str, str], float], bytes] | None = None,
        timeout_seconds: float = 30,
        max_characters: int = 120_000,
    ):
        self._fetcher = fetcher or self._fetch
        self.timeout_seconds = timeout_seconds
        self.max_characters = max_characters

    @staticmethod
    def _fetch(url: str, headers: dict[str, str], timeout: float) -> bytes:
        request = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.read()

    def run(
        self,
        connection: sqlite3.Connection,
        issue_id: str,
        limit: int = 8,
    ) -> PaperContentRun:
        rows = connection.execute(
            """
            SELECT DISTINCT s.item_id, i.value AS arxiv_id
            FROM weekly_selections s
            JOIN research_items r ON r.item_id=s.item_id
            JOIN item_identifiers i
              ON i.item_id=s.item_id AND i.scheme='arxiv'
            WHERE s.issue_id=?
              AND r.item_type='paper'
              AND s.content_role IN ('must_read', 'deep_read', 'library_review')
            ORDER BY s.position
            LIMIT ?
            """,
            (issue_id, limit),
        ).fetchall()
        fetched = cached = failed = 0
        for row in rows:
            arxiv_id = re.sub(r"v\d+$", "", str(row["arxiv_id"]))
            source_url = f"https://arxiv.org/html/{arxiv_id}"
            if connection.execute(
                "SELECT 1 FROM paper_contents WHERE item_id=? AND source_url=?",
                (row["item_id"], source_url),
            ).fetchone():
                cached += 1
                continue
            try:
                payload = self._fetcher(
                    source_url,
                    {
                        "Accept": "text/html",
                        "User-Agent": "weekly-intel/0.1 (OrbitInfer research survey)",
                    },
                    self.timeout_seconds,
                )
                parser = _ArticleTextParser()
                parser.feed(payload.decode("utf-8", errors="replace"))
                content_text = parser.text()[: self.max_characters]
                if len(content_text) < 500:
                    raise ValueError("arXiv HTML did not contain enough paper text")
                connection.execute(
                    """
                    INSERT OR IGNORE INTO paper_contents (
                        content_id, item_id, source_url, content_type,
                        content_text, content_hash, fetched_at, parser_version
                    ) VALUES (?, ?, ?, 'html', ?, ?, ?, ?)
                    """,
                    (
                        str(uuid.uuid4()),
                        row["item_id"],
                        source_url,
                        content_text,
                        sha256_text(content_text),
                        isoformat(utc_now()),
                        self.parser_version,
                    ),
                )
                fetched += 1
            except Exception:
                failed += 1
        return PaperContentRun(
            requested=len(rows),
            fetched=fetched,
            cached=cached,
            failed=failed,
        )
