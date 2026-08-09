from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request
import uuid
from datetime import datetime, timezone
from typing import Any, Callable

from ..contracts import BatchStatus, CollectedDocument, CollectionBatch, CollectionError, CollectionWindow, DocumentType, SourceConfig
from ..utils import json_dumps, sha256_text, utc_now


def _date(value: Any) -> datetime | None:
    if not value:
        return None
    text = str(value).strip()
    for fmt in ("%Y-%m-%d", "%d %B %Y", "%B %Y", "%Y"):
        try:
            return datetime.strptime(text, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            pass
    return None


class IeeeXploreCollector:
    """Collect IEEE Xplore metadata; an API key is required, not a subscription."""

    name = "IeeeXploreCollector"

    def __init__(self, fetcher: Callable[[str, dict[str, str], float], bytes] | None = None):
        self._fetcher = fetcher or self._fetch

    @staticmethod
    def _fetch(url: str, headers: dict[str, str], timeout: float) -> bytes:
        with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=timeout) as response:
            return response.read()

    @staticmethod
    def _document(source: SourceConfig, record: dict[str, Any], discovered_at: datetime) -> CollectedDocument | None:
        article_number = str(record.get("article_number") or "").strip()
        title = str(record.get("title") or "").strip()
        if not article_number or not title:
            return None
        doi = str(record.get("doi") or "").strip().casefold()
        authors = tuple(str(author.get("full_name") or "").strip() for author in ((record.get("authors") or {}).get("authors") or []) if str(author.get("full_name") or "").strip())
        identifiers = {"ieee_article_number": article_number}
        if doi:
            identifiers["doi"] = doi
        access_type = str(record.get("access_type") or record.get("accessType") or "").strip()
        payload = dict(record)
        return CollectedDocument(
            source_id=source.source_id,
            external_id=article_number,
            document_type=DocumentType.PAPER_RECORD,
            canonical_url=str(record.get("html_url") or f"https://ieeexplore.ieee.org/document/{article_number}"),
            title=title,
            published_at=_date(record.get("publication_date")),
            updated_at_source=_date(record.get("publication_date")),
            discovered_at=discovered_at,
            authors=authors,
            summary=record.get("abstract"),
            language="en",
            identifiers=identifiers,
            metadata={
                "version": f"ieee-{article_number}",
                "provider": "ieee_xplore",
                "venue": record.get("publication_title"),
                "publisher": "IEEE",
                "content_type": record.get("content_type"),
                "access_type": access_type,
                "access_status": "open_access" if "open" in access_type.casefold() else "待获取全文",
            },
            raw_payload=payload,
            content_hash=sha256_text(json_dumps(payload)),
        )

    def collect(self, source: SourceConfig, window: CollectionWindow, cursor: str | None = None) -> CollectionBatch:
        run_id = str(uuid.uuid4())
        key_env = str(source.options.get("api_key_env", "IEEE_XPLORE_API_KEY"))
        api_key = os.environ.get(key_env)
        if not api_key:
            return CollectionBatch(
                run_id, source.source_id, BatchStatus.BLOCKED,
                errors=(CollectionError("missing_api_key", f"set {key_env} to enable IEEE Xplore metadata search", False),),
                stats={"queries": 0, "fetched": 0},
            )
        endpoint = str(source.options.get("endpoint", "https://ieeexploreapi.ieee.org/api/v1/search/articles"))
        terms = source.options.get("search_terms", ["satellite computing"])
        max_records = int(source.options.get("max_records", 200))
        timeout = float(source.options.get("timeout_seconds", 30))
        headers = {"Accept": "application/json", "User-Agent": str(source.options.get("user_agent", "weekly-intel/0.1"))}
        documents: dict[str, CollectedDocument] = {}
        errors: list[CollectionError] = []
        fetched = 0
        discovered_at = utc_now()
        for term in terms:
            query = urllib.parse.urlencode({"apikey": api_key, "format": "json", "max_records": max_records, "start_record": 1, "sort_order": "desc", "sort_field": "publication_year", "querytext": str(term), "start_year": window.start.year, "end_year": window.end.year})
            url = f"{endpoint}?{query}"
            try:
                payload = json.loads(self._fetcher(url, headers, timeout).decode("utf-8"))
                records = payload.get("articles") or []
                fetched += len(records)
                for record in records:
                    document = self._document(source, record, discovered_at)
                    if not document or not document.published_at:
                        continue
                    if window.start.date() <= document.published_at.date() <= window.end.date():
                        key = document.identifiers.get("doi") or document.identifiers["ieee_article_number"]
                        documents[key] = document
            except Exception as error:
                errors.append(CollectionError(type(error).__name__, str(error), True, url))
        result = tuple(documents.values())
        status = BatchStatus.PARTIAL if errors and result else BatchStatus.ERROR if errors else BatchStatus.OK if result else BatchStatus.UNCHANGED
        return CollectionBatch(run_id, source.source_id, status, result, errors=tuple(errors), stats={"queries": len(terms), "fetched": fetched, "deduplicated_in_window": len(result)})
