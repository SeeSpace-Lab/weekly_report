from __future__ import annotations

import re
import time
import uuid
import urllib.error
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
OAI = "http://www.openarchives.org/OAI/2.0/"
OAI_ARXIV = "http://arxiv.org/OAI/arXiv/"
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
        categories = source.options.get("categories", [])
        if not categories:
            raise ValueError("arXiv source requires at least one category")
        category_query = " OR ".join(f"cat:{category}" for category in categories)
        search_terms = source.options.get("search_terms", [])
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

    @staticmethod
    def _oai_url(
        source: SourceConfig,
        window: CollectionWindow,
        resumption_token: str | None = None,
    ) -> str:
        endpoint = str(
            source.options.get("oai_endpoint", "https://oaipmh.arxiv.org/oai")
        )
        if resumption_token:
            params = {"verb": "ListRecords", "resumptionToken": resumption_token}
        else:
            params = {
                "verb": "ListRecords",
                "from": window.start.date().isoformat(),
                "until": window.end.date().isoformat(),
                "set": str(source.options.get("oai_set", "cs")),
                "metadataPrefix": "arXiv",
            }
        return f"{endpoint}?{urllib.parse.urlencode(params)}"

    @staticmethod
    def _matches_terms(title: str, summary: str, terms: list[str]) -> bool:
        if not terms:
            return True
        searchable = f"{title} {summary}".casefold()
        for term in terms:
            words = [
                word
                for word in re.findall(r"[a-z0-9]+", str(term).casefold())
                if len(word) > 2
            ]
            required = 1 if len(words) == 1 else 2
            if sum(word in searchable for word in set(words)) >= required:
                return True
        return False

    def _collect_oai(
        self,
        source: SourceConfig,
        window: CollectionWindow,
        run_id: str,
        headers: dict[str, str],
        timeout: float,
        primary_error: Exception,
    ) -> CollectionBatch:
        documents: dict[str, CollectedDocument] = {}
        discovered = utc_now()
        token: str | None = None
        pages = 0
        parsed = 0
        max_pages = max(1, int(source.options.get("oai_max_pages", 3)))
        terms = [str(term) for term in source.options.get("search_terms", [])]
        categories_required = {
            str(category).casefold()
            for category in source.options.get("categories", [])
        }
        try:
            oai_timeout = float(
                source.options.get("oai_timeout_seconds", max(timeout, 60))
            )
            while pages < max_pages:
                url = self._oai_url(source, window, token)
                payload = self._fetcher(url, headers, oai_timeout)
                root = ET.fromstring(payload)
                pages += 1
                for record in root.findall(f".//{{{OAI}}}record"):
                    metadata = record.find(f"{{{OAI}}}metadata")
                    entry = (
                        metadata.find(f"{{{OAI_ARXIV}}}arXiv")
                        if metadata is not None
                        else None
                    )
                    if entry is None:
                        continue
                    parsed += 1
                    arxiv_id = (entry.findtext(f"{{{OAI_ARXIV}}}id") or "").strip()
                    title = " ".join(
                        (entry.findtext(f"{{{OAI_ARXIV}}}title") or "").split()
                    )
                    summary = " ".join(
                        (entry.findtext(f"{{{OAI_ARXIV}}}abstract") or "").split()
                    )
                    categories = (
                        entry.findtext(f"{{{OAI_ARXIV}}}categories") or ""
                    ).split()
                    if not arxiv_id or not title:
                        continue
                    if categories_required and not any(
                        category.casefold() in categories_required
                        for category in categories
                    ):
                        continue
                    if not self._matches_terms(title, summary, terms):
                        continue
                    created = _parse_datetime(
                        (entry.findtext(f"{{{OAI_ARXIV}}}created") or "")
                        + "T00:00:00Z"
                    )
                    updated_text = entry.findtext(f"{{{OAI_ARXIV}}}updated")
                    updated = (
                        _parse_datetime(updated_text + "T00:00:00Z")
                        if updated_text
                        else None
                    )
                    event_time = updated or created
                    if not event_time or not window.start <= event_time <= window.end:
                        continue
                    authors = []
                    for author in entry.findall(
                        f"{{{OAI_ARXIV}}}authors/{{{OAI_ARXIV}}}author"
                    ):
                        keyname = author.findtext(f"{{{OAI_ARXIV}}}keyname") or ""
                        forenames = author.findtext(f"{{{OAI_ARXIV}}}forenames") or ""
                        name = " ".join(part for part in (forenames, keyname) if part)
                        if name:
                            authors.append(name)
                    doi = (entry.findtext(f"{{{OAI_ARXIV}}}doi") or "").strip()
                    identifiers = {"arxiv": arxiv_id}
                    if doi:
                        identifiers["doi"] = doi.casefold()
                    raw = {
                        "id": arxiv_id,
                        "created": isoformat(created),
                        "updated": isoformat(updated),
                        "title": title,
                        "summary": summary,
                        "authors": authors,
                        "categories": categories,
                    }
                    documents[arxiv_id] = CollectedDocument(
                        source_id=source.source_id,
                        external_id=arxiv_id,
                        document_type=DocumentType.PAPER_RECORD,
                        canonical_url=f"https://arxiv.org/abs/{arxiv_id}",
                        title=title,
                        published_at=created,
                        updated_at_source=updated,
                        discovered_at=discovered,
                        authors=authors,
                        summary=summary,
                        language="en",
                        identifiers=identifiers,
                        metadata={
                            "version": f"oai-{isoformat(event_time)}",
                            "categories": categories,
                            "primary_category": categories[0] if categories else None,
                            "provider_mode": "oai_fallback",
                        },
                        raw_payload=raw,
                        content_hash=sha256_text(json_dumps(raw)),
                    )
                token_node = root.find(f".//{{{OAI}}}resumptionToken")
                token = (
                    token_node.text.strip()
                    if token_node is not None and token_node.text
                    else None
                )
                if not token:
                    break
        except Exception as fallback_error:
            return CollectionBatch(
                run_id=run_id,
                source_id=source.source_id,
                status=BatchStatus.ERROR,
                errors=(
                    CollectionError(
                        code="arxiv_primary_and_oai_failed",
                        message=(
                            f"Primary API failed ({primary_error}); "
                            f"OAI fallback failed ({fallback_error})"
                        ),
                        retryable=True,
                        target=str(source.options.get("oai_endpoint", "")),
                    ),
                ),
                stats={"provider_mode": "oai_fallback", "pages": pages},
            )
        result = tuple(documents.values())
        return CollectionBatch(
            run_id=run_id,
            source_id=source.source_id,
            status=BatchStatus.OK if result else BatchStatus.UNCHANGED,
            documents=result,
            next_cursor=isoformat(window.end),
            stats={
                "provider_mode": "oai_fallback",
                "pages": pages,
                "parsed": parsed,
                "in_window": len(result),
                "primary_error": type(primary_error).__name__,
            },
        )

    def collect(
        self,
        source: SourceConfig,
        window: CollectionWindow,
        cursor: str | None = None,
    ) -> CollectionBatch:
        run_id = str(uuid.uuid4())
        try:
            url = self.build_url(source, window)
            timeout = float(source.options.get("timeout_seconds", 30))
            headers = {
                "User-Agent": str(
                    source.options.get(
                        "user_agent", "weekly-intel/0.1 research survey"
                    )
                )
            }
            max_retries = max(0, int(source.options.get("max_retries", 3)))
            backoff = max(
                0.0, float(source.options.get("retry_backoff_seconds", 3))
            )
            for attempt in range(max_retries + 1):
                try:
                    payload = self._fetcher(url, headers, timeout)
                    break
                except urllib.error.HTTPError as error:
                    if error.code not in {429, 500, 502, 503, 504}:
                        raise
                    if attempt >= max_retries:
                        raise
                    retry_after = error.headers.get("Retry-After") if error.headers else None
                    try:
                        delay = float(retry_after) if retry_after else backoff * (2**attempt)
                    except ValueError:
                        delay = backoff * (2**attempt)
                    self._sleeper(max(0.0, delay))
                except (urllib.error.URLError, TimeoutError):
                    if attempt >= max_retries:
                        raise
                    self._sleeper(backoff * (2**attempt))
            return self.parse(payload, source, window, run_id)
        except urllib.error.HTTPError as error:
            if source.options.get("oai_fallback", False):
                return self._collect_oai(
                    source, window, run_id, headers, timeout, error
                )
            return CollectionBatch(
                run_id=run_id,
                source_id=source.source_id,
                status=BatchStatus.ERROR,
                errors=(
                    CollectionError(
                        code="rate_limited" if error.code == 429 else "http_error",
                        message=f"arXiv HTTP {error.code} after retries",
                        retryable=error.code in {429, 500, 502, 503, 504},
                        target=str(source.options.get("endpoint", "")),
                        details={"http_status": error.code},
                    ),
                ),
            )
        except Exception as error:
            if source.options.get("oai_fallback", False):
                return self._collect_oai(
                    source, window, run_id, headers, timeout, error
                )
            return CollectionBatch(
                run_id=run_id,
                source_id=source.source_id,
                status=BatchStatus.ERROR,
                errors=(
                    CollectionError(
                        code=type(error).__name__,
                        message=str(error),
                        retryable=True,
                        target=str(source.options.get("endpoint", "")),
                    ),
                ),
            )
