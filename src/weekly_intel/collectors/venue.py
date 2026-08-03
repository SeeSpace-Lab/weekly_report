from __future__ import annotations

import html
import re
import urllib.error
import urllib.request
import uuid
from html.parser import HTMLParser
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
from .http import fetch_with_retry


class _PageParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.title_parts: list[str] = []
        self.text_parts: list[str] = []
        self.description: str | None = None
        self._in_title = False
        self._ignored_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_dict = dict(attrs)
        if tag in {"script", "style", "svg", "noscript"}:
            self._ignored_depth += 1
        if tag == "title":
            self._in_title = True
        if tag == "meta":
            key = (
                attrs_dict.get("property")
                or attrs_dict.get("name")
                or ""
            ).casefold()
            if key in {"description", "og:description"} and attrs_dict.get(
                "content"
            ):
                self.description = attrs_dict["content"]

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "svg", "noscript"} and self._ignored_depth:
            self._ignored_depth -= 1
        if tag == "title":
            self._in_title = False

    def handle_data(self, data: str) -> None:
        if self._ignored_depth:
            return
        if self._in_title:
            self.title_parts.append(data)
        self.text_parts.append(data)

    @property
    def title(self) -> str | None:
        value = re.sub(r"\s+", " ", " ".join(self.title_parts)).strip()
        return html.unescape(value) or None

    @property
    def text(self) -> str:
        return html.unescape(
            re.sub(r"\s+", " ", " ".join(self.text_parts)).strip()
        )


class VenueCollector:
    name = "VenueCollector"

    def __init__(
        self,
        fetcher: Callable[[str, dict[str, str], float], bytes] | None = None,
    ):
        self._fetcher = fetcher or self._fetch

    @staticmethod
    def _fetch(url: str, headers: dict[str, str], timeout: float) -> bytes:
        request = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.read()

    def collect(
        self,
        source: SourceConfig,
        window: CollectionWindow,
        cursor: str | None = None,
    ) -> CollectionBatch:
        run_id = str(uuid.uuid4())
        pages = source.options.get("pages", [])
        timeout = float(source.options.get("timeout_seconds", 30))
        max_retries = int(source.options.get("max_retries", 2))
        retry_backoff = float(source.options.get("retry_backoff_seconds", 2))
        headers = {
            "Accept": "text/html,application/xhtml+xml",
            "User-Agent": str(
                source.options.get("user_agent", "weekly-intel/0.1")
            ),
        }
        discovered = utc_now()
        documents = []
        errors = []
        for page in pages:
            url = str(page["url"])
            try:
                payload = fetch_with_retry(
                    self._fetcher,
                    url,
                    headers,
                    timeout,
                    max_retries=max_retries,
                    backoff_seconds=retry_backoff,
                )
                decoded = payload.decode("utf-8", errors="replace")
                parser = _PageParser()
                parser.feed(decoded)
                content_text = parser.text[:50000]
                content_hash = sha256_text(content_text)
                venue_name = str(page["name"])
                documents.append(
                    CollectedDocument(
                        source_id=source.source_id,
                        external_id=str(page["id"]),
                        document_type=DocumentType.VENUE_EVENT,
                        canonical_url=url,
                        title=parser.title or venue_name,
                        published_at=None,
                        updated_at_source=discovered,
                        discovered_at=discovered,
                        summary=parser.description or content_text[:600],
                        content_text=content_text,
                        language="en",
                        identifiers={
                            "venue_paper": f"venue-page:{page['id']}"
                        },
                        metadata={
                            "item_title": venue_name,
                            "venue_id": page["id"],
                            "venue_name": venue_name,
                            "category": page.get("category"),
                            "event_type": "official_page_snapshot",
                            "version": content_hash[:16],
                            "official": True,
                        },
                        raw_payload={
                            "url": url,
                            "page_title": parser.title,
                            "description": parser.description,
                        },
                        content_hash=content_hash,
                    )
                )
            except urllib.error.HTTPError as error:
                errors.append(
                    CollectionError(
                        code="http_error",
                        message=f"Venue page HTTP {error.code}",
                        retryable=True,
                        target=url,
                    )
                )
            except Exception as error:
                errors.append(
                    CollectionError(
                        code=type(error).__name__,
                        message=str(error),
                        retryable=True,
                        target=url,
                    )
                )
        if errors and documents:
            status = BatchStatus.PARTIAL
        elif errors:
            status = BatchStatus.ERROR
        elif documents:
            status = BatchStatus.OK
        else:
            status = BatchStatus.UNCHANGED
        return CollectionBatch(
            run_id=run_id,
            source_id=source.source_id,
            status=status,
            documents=tuple(documents),
            next_cursor=isoformat(discovered) if documents else cursor,
            errors=tuple(errors),
            stats={
                "configured_pages": len(pages),
                "fetched": len(documents),
                "failed": len(errors),
            },
        )
