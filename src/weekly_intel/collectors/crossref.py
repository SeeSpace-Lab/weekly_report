from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
import uuid
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any, Callable

from ..contracts import (
    BatchStatus,
    CollectedDocument,
    CollectionBatch,
    CollectionError,
    CollectionWindow,
    DocumentType,
    SourceConfig,
)
from ..utils import isoformat, json_dumps, sha256_text, utc_now


def _date_parts(value: Any) -> datetime | None:
    try:
        parts = value["date-parts"][0]
        year = int(parts[0])
        month = int(parts[1]) if len(parts) > 1 else 1
        day = int(parts[2]) if len(parts) > 2 else 1
        return datetime(year, month, day, tzinfo=timezone.utc)
    except (KeyError, IndexError, TypeError, ValueError):
        return None


def _timestamp(value: Any) -> datetime | None:
    if isinstance(value, dict) and value.get("timestamp") is not None:
        return datetime.fromtimestamp(
            float(value["timestamp"]) / 1000, tz=timezone.utc
        )
    if isinstance(value, dict) and value.get("date-time"):
        return datetime.fromisoformat(
            str(value["date-time"]).replace("Z", "+00:00")
        ).astimezone(timezone.utc)
    return None


class CrossrefCollector:
    """Collect DOI metadata as a secondary identity and venue signal."""

    name = "CrossrefCollector"

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

    @staticmethod
    def _url(
        endpoint: str,
        term: str,
        window: CollectionWindow,
        rows: int,
    ) -> str:
        params = urllib.parse.urlencode(
            {
                "query.bibliographic": term,
                "filter": (
                    f"from-index-date:{window.start.date().isoformat()},"
                    f"until-index-date:{window.end.date().isoformat()}"
                ),
                "sort": "indexed",
                "order": "desc",
                "rows": str(rows),
            }
        )
        return f"{endpoint.rstrip('/')}/works?{params}"

    @staticmethod
    def _document(
        source: SourceConfig,
        record: dict[str, Any],
        discovered_at: datetime,
    ) -> CollectedDocument | None:
        doi = str(record.get("DOI") or "").strip().casefold()
        titles = record.get("title") or []
        title = str(titles[0] if titles else "").strip()
        if not doi or not title:
            return None
        authors = []
        for author in record.get("author") or []:
            name = " ".join(
                part
                for part in (
                    str(author.get("given") or "").strip(),
                    str(author.get("family") or "").strip(),
                )
                if part
            )
            if name:
                authors.append(name)
        published = _date_parts(record.get("published"))
        indexed = _timestamp(record.get("indexed"))
        created = _timestamp(record.get("created"))
        updated = indexed or created or published
        canonical_url = str(
            record.get("URL") or f"https://doi.org/{doi}"
        )
        payload = dict(record)
        venue = (record.get("container-title") or [None])[0]
        return CollectedDocument(
            source_id=source.source_id,
            external_id=doi,
            document_type=DocumentType.PAPER_RECORD,
            canonical_url=canonical_url,
            title=title,
            published_at=published,
            updated_at_source=updated,
            discovered_at=discovered_at,
            authors=tuple(authors),
            summary=record.get("abstract"),
            language="en",
            identifiers={"doi": doi},
            metadata={
                "version": f"crossref-{isoformat(updated) or 'unknown'}",
                "provider": "crossref",
                "venue": venue,
                "work_type": record.get("type"),
                "subtype": record.get("subtype"),
                "subjects": record.get("subject") or [],
                "licenses": record.get("license") or [],
            },
            raw_payload=payload,
            content_hash=sha256_text(json_dumps(payload)),
        )

    def collect(
        self,
        source: SourceConfig,
        window: CollectionWindow,
        cursor: str | None = None,
    ) -> CollectionBatch:
        run_id = str(uuid.uuid4())
        endpoint = str(
            source.options.get("endpoint", "https://api.crossref.org")
        )
        terms = source.options.get(
            "search_terms",
            [
                "large language model inference",
                "LLM serving",
                "energy efficient inference",
            ],
        )
        rows = int(source.options.get("rows_per_query", 50))
        timeout = float(source.options.get("timeout_seconds", 30))
        headers = {
            "Accept": "application/json",
            "User-Agent": str(
                source.options.get(
                    "user_agent",
                    "weekly-intel/0.1 (mailto:research@example.com)",
                )
            ),
        }
        documents: dict[str, CollectedDocument] = {}
        errors: list[CollectionError] = []
        fetched = 0
        latest: datetime | None = None
        discovered_at = utc_now()
        for term in terms:
            url = self._url(endpoint, str(term), window, rows)
            try:
                payload = json.loads(
                    self._fetcher(url, headers, timeout).decode("utf-8")
                )
                records = payload.get("message", {}).get("items", [])
                fetched += len(records)
                for record in records:
                    document = self._document(source, record, discovered_at)
                    if document is None:
                        continue
                    event_time = (
                        document.updated_at_source or document.published_at
                    )
                    if event_time:
                        latest = max(latest or event_time, event_time)
                    if event_time and window.start <= event_time <= window.end:
                        documents[document.identifiers["doi"]] = document
            except urllib.error.HTTPError as error:
                errors.append(
                    CollectionError(
                        code=(
                            "rate_limited"
                            if error.code in {403, 429}
                            else "http_error"
                        ),
                        message=f"Crossref HTTP {error.code}",
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
        result = tuple(documents.values())
        if errors and result:
            status = BatchStatus.PARTIAL
        elif errors:
            status = BatchStatus.ERROR
        elif result:
            status = BatchStatus.OK
        else:
            status = BatchStatus.UNCHANGED
        return CollectionBatch(
            run_id=run_id,
            source_id=source.source_id,
            status=status,
            documents=result,
            next_cursor=isoformat(latest),
            errors=tuple(errors),
            stats={
                "queries": len(terms),
                "fetched": fetched,
                "deduplicated_in_window": len(result),
            },
        )
