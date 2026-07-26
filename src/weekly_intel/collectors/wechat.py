from __future__ import annotations

import html
import os
import re
import urllib.error
import urllib.request
import uuid
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
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
CONTENT = "http://purl.org/rss/1.0/modules/content/"
ARXIV_RE = re.compile(
    r"(?:arxiv\.org/(?:abs|pdf)/|arXiv:\s*)(\d{4}\.\d{4,5})(?:v\d+)?",
    re.IGNORECASE,
)


def _plain_text(value: str | None) -> str | None:
    if not value:
        return None
    text = re.sub(r"<[^>]+>", " ", value)
    return re.sub(r"\s+", " ", html.unescape(text)).strip() or None


def _date(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return parsedate_to_datetime(value).astimezone(timezone.utc)
    except (TypeError, ValueError):
        try:
            return datetime.fromisoformat(
                value.replace("Z", "+00:00")
            ).astimezone(timezone.utc)
        except ValueError:
            return None


class WechatPoolCollector:
    name = "WechatPoolCollector"

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

    def _feed_url(self, source: SourceConfig) -> str | None:
        if source.options.get("feed_url"):
            return str(source.options["feed_url"])
        env_name = source.options.get("feed_url_env")
        if env_name and os.environ.get(str(env_name)):
            return os.environ[str(env_name)]
        base = os.environ.get("WECHAT_FEED_BASE_URL")
        account_id = source.options.get("account_id")
        if base and account_id:
            return f"{base.rstrip('/')}/{account_id}.xml"
        return None

    def parse(
        self,
        payload: bytes,
        source: SourceConfig,
        window: CollectionWindow,
        run_id: str,
    ) -> CollectionBatch:
        root = ET.fromstring(payload)
        discovered = utc_now()
        entries: list[dict[str, str | None]] = []
        if root.tag == f"{{{ATOM}}}feed":
            for entry in root.findall(f"{{{ATOM}}}entry"):
                link = None
                for node in entry.findall(f"{{{ATOM}}}link"):
                    if node.attrib.get("rel", "alternate") == "alternate":
                        link = node.attrib.get("href")
                        break
                entries.append(
                    {
                        "id": entry.findtext(f"{{{ATOM}}}id"),
                        "title": entry.findtext(f"{{{ATOM}}}title"),
                        "link": link,
                        "published": entry.findtext(f"{{{ATOM}}}published"),
                        "updated": entry.findtext(f"{{{ATOM}}}updated"),
                        "summary": entry.findtext(f"{{{ATOM}}}summary"),
                        "content": entry.findtext(f"{{{ATOM}}}content"),
                    }
                )
        else:
            for item in root.findall("./channel/item"):
                entries.append(
                    {
                        "id": item.findtext("guid"),
                        "title": item.findtext("title"),
                        "link": item.findtext("link"),
                        "published": item.findtext("pubDate"),
                        "updated": None,
                        "summary": item.findtext("description"),
                        "content": item.findtext(f"{{{CONTENT}}}encoded"),
                    }
                )
        documents = []
        latest_seen = None
        for entry in entries:
            link = entry["link"]
            title = _plain_text(entry["title"])
            if not link or not title:
                continue
            published = _date(entry["published"])
            updated = _date(entry["updated"])
            event_time = updated or published
            if event_time:
                latest_seen = max(latest_seen or event_time, event_time)
            if not event_time or not (window.start <= event_time <= window.end):
                continue
            content_text = _plain_text(entry["content"])
            summary = _plain_text(entry["summary"]) or (
                content_text[:500] if content_text else None
            )
            searchable = " ".join(
                value or ""
                for value in (entry["content"], entry["summary"], link)
            )
            related_arxiv_ids = sorted(set(ARXIV_RE.findall(searchable)))
            raw = dict(entry)
            external_id = entry["id"] or link
            documents.append(
                CollectedDocument(
                    source_id=source.source_id,
                    external_id=str(external_id),
                    document_type=DocumentType.REVIEW_ARTICLE,
                    canonical_url=link,
                    title=title,
                    published_at=published,
                    updated_at_source=updated,
                    discovered_at=discovered,
                    summary=summary,
                    content_text=content_text,
                    language="zh",
                    identifiers={"url_fingerprint": sha256_text(link)},
                    metadata={
                        "item_title": title,
                        "source_account": source.name,
                        "account_id": source.options.get("account_id"),
                        "account_alias": source.options.get("account_alias"),
                        "feed_provider": source.options.get("provider"),
                        "related_arxiv_ids": related_arxiv_ids,
                    },
                    raw_payload=raw,
                    content_hash=sha256_text(json_dumps(raw)),
                )
            )
        return CollectionBatch(
            run_id=run_id,
            source_id=source.source_id,
            status=BatchStatus.OK if documents else BatchStatus.UNCHANGED,
            documents=documents,
            next_cursor=isoformat(latest_seen),
            stats={"feed_entries": len(entries), "in_window": len(documents)},
        )

    def collect(
        self,
        source: SourceConfig,
        window: CollectionWindow,
        cursor: str | None = None,
    ) -> CollectionBatch:
        run_id = str(uuid.uuid4())
        feed_url = self._feed_url(source)
        if not feed_url:
            return CollectionBatch(
                run_id=run_id,
                source_id=source.source_id,
                status=BatchStatus.BLOCKED,
                errors=(
                    CollectionError(
                        code="subscription_not_configured",
                        message=(
                            f"No RSS/Atom adapter configured for {source.name}"
                        ),
                        retryable=False,
                        target=source.source_id,
                    ),
                ),
            )
        try:
            payload = self._fetcher(
                feed_url,
                {
                    "Accept": "application/rss+xml, application/atom+xml, application/xml",
                    "User-Agent": str(
                        source.options.get("user_agent", "weekly-intel/0.1")
                    ),
                },
                float(source.options.get("timeout_seconds", 30)),
            )
            return self.parse(payload, source, window, run_id)
        except urllib.error.HTTPError as error:
            return CollectionBatch(
                run_id=run_id,
                source_id=source.source_id,
                status=(
                    BatchStatus.BLOCKED
                    if error.code in {401, 403, 429}
                    else BatchStatus.ERROR
                ),
                errors=(
                    CollectionError(
                        code="feed_access_error",
                        message=f"Feed HTTP {error.code}",
                        retryable=True,
                        target=feed_url,
                    ),
                ),
            )
        except Exception as error:
            return CollectionBatch(
                run_id=run_id,
                source_id=source.source_id,
                status=BatchStatus.ERROR,
                errors=(
                    CollectionError(
                        code=type(error).__name__,
                        message=str(error),
                        retryable=True,
                        target=feed_url,
                    ),
                ),
            )
