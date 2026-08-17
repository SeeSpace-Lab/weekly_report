from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
import uuid
from datetime import datetime, timezone
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
from ..utils import json_dumps, sha256_text, utc_now


def _date(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value)[:10]).replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def _abstract(index: Any) -> str | None:
    if not isinstance(index, dict):
        return None
    words: list[tuple[int, str]] = []
    for word, positions in index.items():
        for position in positions or []:
            words.append((int(position), str(word)))
    return " ".join(word for _, word in sorted(words)) or None


class OpenAlexCollector:
    """Search the cross-publisher scholarly graph for weekly paper metadata."""

    name = "OpenAlexCollector"

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
        per_page: int,
        cursor: str,
        api_key: str | None,
    ) -> str:
        query = {
            "search": term,
            "filter": (
                f"from_publication_date:{window.start.date().isoformat()},"
                f"to_publication_date:{window.end.date().isoformat()}"
            ),
            "per-page": str(per_page),
            "cursor": cursor,
        }
        if api_key:
            query["api_key"] = api_key
        return f"{endpoint.rstrip('/')}?{urllib.parse.urlencode(query)}"

    @staticmethod
    def _document(
        source: SourceConfig,
        record: dict[str, Any],
        discovered_at: datetime,
    ) -> CollectedDocument | None:
        openalex_id = str(record.get("id") or "").rsplit("/", 1)[-1]
        title = str(record.get("display_name") or record.get("title") or "").strip()
        if not openalex_id or not title:
            return None
        doi = str(record.get("doi") or "").removeprefix("https://doi.org/").casefold()
        primary = record.get("primary_location") or {}
        source_record = primary.get("source") or {}
        best_oa = record.get("best_oa_location") or {}
        canonical_url = str(
            primary.get("landing_page_url")
            or record.get("doi")
            or record.get("id")
        )
        authors = tuple(
            str((authorship.get("author") or {}).get("display_name") or "").strip()
            for authorship in record.get("authorships") or []
            if str((authorship.get("author") or {}).get("display_name") or "").strip()
        )
        identifiers = {"openalex": openalex_id}
        if doi:
            identifiers["doi"] = doi
        is_oa = bool((record.get("open_access") or {}).get("is_oa"))
        payload = dict(record)
        abstract = _abstract(record.get("abstract_inverted_index"))
        if best_oa.get("pdf_url"):
            access_status = "已获取全文"
        elif abstract:
            access_status = "待获取全文｜基于摘要初筛"
        else:
            access_status = "待获取全文与摘要｜仅题目判断"
        return CollectedDocument(
            source_id=source.source_id,
            external_id=openalex_id,
            document_type=DocumentType.PAPER_RECORD,
            canonical_url=canonical_url,
            title=title,
            published_at=_date(record.get("publication_date")),
            updated_at_source=_date(record.get("updated_date")),
            discovered_at=discovered_at,
            authors=authors,
            summary=abstract,
            language=record.get("language"),
            identifiers=identifiers,
            metadata={
                "version": f"openalex-{record.get('updated_date') or 'unknown'}",
                "provider": "openalex",
                "venue": source_record.get("display_name"),
                "publisher": source_record.get("host_organization_name"),
                "work_type": record.get("type"),
                "is_oa": is_oa,
                "access_status": access_status,
                "evidence_status": (
                    "full_text"
                    if best_oa.get("pdf_url")
                    else "abstract_screened" if abstract else "title_only"
                ),
                "pdf_url": best_oa.get("pdf_url"),
                "cited_by_count": record.get("cited_by_count"),
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
        endpoint = str(source.options.get("endpoint", "https://api.openalex.org/works"))
        terms = source.options.get("search_terms", ["satellite computing"])
        per_page = int(source.options.get("per_page", 100))
        max_pages = int(source.options.get("max_pages", 3))
        timeout = float(source.options.get("timeout_seconds", 30))
        key_env = str(source.options.get("api_key_env", "OPENALEX_API_KEY"))
        api_key = os.environ.get(key_env)
        if not api_key:
            return CollectionBatch(
                run_id,
                source.source_id,
                BatchStatus.BLOCKED,
                errors=(CollectionError(
                    "missing_api_key",
                    f"set {key_env} to enable OpenAlex metadata search",
                    False,
                ),),
                stats={"queries": 0, "requests": 0, "fetched": 0},
            )
        headers = {"Accept": "application/json", "User-Agent": str(source.options.get("user_agent", "weekly-intel/0.1"))}
        documents: dict[str, CollectedDocument] = {}
        errors: list[CollectionError] = []
        requests = fetched = 0
        discovered_at = utc_now()
        for term in terms:
            next_cursor = "*"
            for _ in range(max_pages):
                url = self._url(endpoint, str(term), window, per_page, next_cursor, api_key)
                try:
                    payload = json.loads(self._fetcher(url, headers, timeout).decode("utf-8"))
                    requests += 1
                    records = payload.get("results") or []
                    fetched += len(records)
                    for record in records:
                        document = self._document(source, record, discovered_at)
                        if document and document.published_at and window.start.date() <= document.published_at.date() <= window.end.date():
                            key = document.identifiers.get("doi") or document.identifiers["openalex"]
                            documents[key] = document
                    next_cursor = str((payload.get("meta") or {}).get("next_cursor") or "")
                    if not records or not next_cursor:
                        break
                except Exception as error:
                    errors.append(CollectionError(type(error).__name__, str(error), True, url))
                    break
        result = tuple(documents.values())
        status = BatchStatus.PARTIAL if errors and result else BatchStatus.ERROR if errors else BatchStatus.OK if result else BatchStatus.UNCHANGED
        return CollectionBatch(run_id, source.source_id, status, result, errors=tuple(errors), stats={"queries": len(terms), "requests": requests, "fetched": fetched, "deduplicated_in_window": len(result)})
