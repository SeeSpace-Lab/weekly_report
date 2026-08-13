from __future__ import annotations

import re
import time
import uuid
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from typing import Callable

from ..contracts import (
    BatchStatus,
    CollectionBatch,
    CollectionError,
    CollectionWindow,
    CollectedDocument,
    DocumentType,
    SourceConfig,
)
from ..utils import isoformat, json_dumps, sha256_text, utc_now

ATOM = "http://www.w3.org/2005/Atom"
ARXIV = "http://arxiv.org/schemas/atom"
NS = {"atom": ATOM, "arxiv": ARXIV}
ARXIV_ID_RE = re.compile(r"(?P<base>[^/]+?)(?P<version>v\d+)?$")


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(
        timezone.utc
    )


def _text(element: ET.Element, path: str) -> str | None:
    node = element.find(path, NS)
    return node.text.strip() if node is not None and node.text else None


class ArxivCollector:
    name = "ArxivCollector"

    def __init__(
        self,
        fetcher: Callable[[str, dict[str, str], float], bytes] | None = None,
        sleeper: Callable[[float], None] | None = None,
    ):
        self._fetcher = fetcher or self._fetch
        self._sleeper = sleeper or time.sleep

    @staticmethod
    def _fetch(url: str, headers: dict[str, str], timeout: float) -> bytes:
        request = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.read()

    def build_url(
        self, source: SourceConfig, window: CollectionWindow
    ) -> str:
        return self._build_url(
            source,
            source.options.get("categories", []),
            source.options.get("search_terms", []),
        )

    def build_urls(
        self, source: SourceConfig, window: CollectionWindow
    ) -> tuple[str, ...]:
        search_terms = list(source.options.get("search_terms", []))
        terms_per_query = int(
            source.options.get("search_terms_per_query", 0)
        )
        if not search_terms or terms_per_query <= 0:
            return (self.build_url(source, window),)
        return tuple(
            self._build_url(
                source,
                source.options.get("categories", []),
                search_terms[offset : offset + terms_per_query],
            )
            for offset in range(0, len(search_terms), terms_per_query)
        )

    @staticmethod
    def _build_url(
        source: SourceConfig,
        categories: list[str] | tuple[str, ...],
        search_terms: list[str] | tuple[str, ...],
    ) -> str:
        if not categories:
            raise ValueError("arXiv source requires at least one category")
        category_query = " OR ".join(f"cat:{category}" for category in categories)
        query = f"({category_query})"
        if search_terms:
            term_query = " OR ".join(
                f'all:"{str(term).replace(chr(34), "")}"'
                for term in search_terms
            )
            query = f"{query} AND ({term_query})"
        max_results = int(source.options.get("max_results", 200))
        params = {
            "search_query": query,
            "start": "0",
            "max_results": str(max_results),
            "sortBy": "lastUpdatedDate",
            "sortOrder": "descending",
        }
        endpoint = str(
            source.options.get("endpoint", "https://export.arxiv.org/api/query")
        )
        return f"{endpoint}?{urllib.parse.urlencode(params)}"

    def parse(
        self,
        payload: bytes,
        source: SourceConfig,
        window: CollectionWindow,
        run_id: str,
    ) -> CollectionBatch:
        root = ET.fromstring(payload)
        discovered_at = utc_now()
        documents: list[CollectedDocument] = []
        latest_seen: datetime | None = None
        parsed_count = 0
        for entry in root.findall("atom:entry", NS):
            parsed_count += 1
            entry_url = _text(entry, "atom:id")
            if not entry_url:
                continue
            identifier = entry_url.rstrip("/").rsplit("/", 1)[-1]
            match = ARXIV_ID_RE.search(identifier)
            if not match:
                continue
            base_id = match.group("base")
            version = match.group("version") or "v1"
            published = _parse_datetime(_text(entry, "atom:published"))
            updated = _parse_datetime(_text(entry, "atom:updated"))
            event_time = updated or published
            if event_time:
                latest_seen = max(latest_seen or event_time, event_time)
            if not event_time or not (window.start <= event_time <= window.end):
                continue
            title = " ".join((_text(entry, "atom:title") or "").split())
            summary = " ".join((_text(entry, "atom:summary") or "").split())
            authors = [
                name.text.strip()
                for name in entry.findall("atom:author/atom:name", NS)
                if name.text
            ]
            categories = [
                node.attrib["term"]
                for node in entry.findall("atom:category", NS)
                if "term" in node.attrib
            ]
            doi = _text(entry, "arxiv:doi")
            pdf_url = None
            for link in entry.findall("atom:link", NS):
                if link.attrib.get("title") == "pdf":
                    pdf_url = link.attrib.get("href")
                    break
            identifiers = {"arxiv": base_id}
            if doi:
                identifiers["doi"] = doi.lower()
            primary_category = entry.find("arxiv:primary_category", NS)
            metadata = {
                "version": version,
                "categories": categories,
                "primary_category": (
                    primary_category.attrib.get("term")
                    if primary_category is not None
                    else None
                ),
                "comment": _text(entry, "arxiv:comment"),
                "journal_ref": _text(entry, "arxiv:journal_ref"),
                "pdf_url": pdf_url,
            }
            raw_payload = {
                "id": entry_url,
                "published": isoformat(published),
                "updated": isoformat(updated),
                "title": title,
                "summary": summary,
                "authors": authors,
                "metadata": metadata,
            }
            content_hash = sha256_text(json_dumps(raw_payload))
            documents.append(
                CollectedDocument(
                    source_id=source.source_id,
                    external_id=identifier,
                    document_type=DocumentType.PAPER_RECORD,
                    canonical_url=f"https://arxiv.org/abs/{base_id}",
                    title=title,
                    published_at=published,
                    updated_at_source=updated,
                    discovered_at=discovered_at,
                    authors=authors,
                    summary=summary,
                    language="en",
                    identifiers=identifiers,
                    metadata=metadata,
                    raw_payload=raw_payload,
                    content_hash=content_hash,
                )
            )
        status = BatchStatus.OK if documents else BatchStatus.UNCHANGED
        return CollectionBatch(
            run_id=run_id,
            source_id=source.source_id,
            status=status,
            documents=documents,
            next_cursor=isoformat(latest_seen),
            stats={"parsed": parsed_count, "in_window": len(documents)},
        )

    def collect(
        self,
        source: SourceConfig,
        window: CollectionWindow,
        cursor: str | None = None,
    ) -> CollectionBatch:
        run_id = str(uuid.uuid4())
        timeout = float(source.options.get("timeout_seconds", 30))
        headers = {
            "User-Agent": str(
                source.options.get(
                    "user_agent", "weekly-intel/0.1 research survey"
                )
            )
        }
        endpoint = str(source.options.get("endpoint", ""))
        errors: list[CollectionError] = []
        documents: dict[str, CollectedDocument] = {}
        parsed_count = 0
        matched_count = 0
        successful_queries = 0
        latest_cursor: str | None = None
        try:
            urls = self.build_urls(source, window)
        except Exception as error:
            return CollectionBatch(
                run_id=run_id,
                source_id=source.source_id,
                status=BatchStatus.ERROR,
                errors=(
                    CollectionError(
                        code=type(error).__name__,
                        message=str(error),
                        retryable=False,
                        target=endpoint,
                    ),
                ),
            )

        delay = float(source.options.get("request_delay_seconds", 0))
        for index, url in enumerate(urls):
            try:
                payload = self._fetcher(url, headers, timeout)
                batch = self.parse(payload, source, window, run_id)
                successful_queries += 1
                parsed_count += int(batch.stats.get("parsed", 0))
                matched_count += int(batch.stats.get("in_window", 0))
                for document in batch.documents:
                    documents[document.idempotency_key] = document
                if batch.next_cursor and (
                    latest_cursor is None
                    or batch.next_cursor > latest_cursor
                ):
                    latest_cursor = batch.next_cursor
            except Exception as error:
                errors.append(
                    CollectionError(
                        code=type(error).__name__,
                        message=str(error),
                        retryable=True,
                        target=endpoint,
                        details={"query_index": index + 1},
                    )
                )
            if delay > 0 and index + 1 < len(urls):
                self._sleeper(delay)

        collected = tuple(documents.values())
        if errors and not successful_queries:
            status = BatchStatus.ERROR
        elif errors:
            status = BatchStatus.PARTIAL
        elif collected:
            status = BatchStatus.OK
        else:
            status = BatchStatus.UNCHANGED
        return CollectionBatch(
            run_id=run_id,
            source_id=source.source_id,
            status=status,
            documents=collected,
            next_cursor=latest_cursor,
            errors=tuple(errors),
            stats={
                "queries": len(urls),
                "successful_queries": successful_queries,
                "failed_queries": len(errors),
                "parsed": parsed_count,
                "in_window_before_deduplication": matched_count,
                "in_window": len(collected),
            },
        )
