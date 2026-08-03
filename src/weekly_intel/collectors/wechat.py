from __future__ import annotations

import html
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
import xml.etree.ElementTree as ET
from dataclasses import replace
from datetime import datetime, timedelta, timezone
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
        sleeper: Callable[[float], None] | None = None,
    ):
        self._fetcher = fetcher or self._fetch
        self._sleeper = sleeper or time.sleep

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

    def _refresh_url(
        self, source: SourceConfig, feed_url: str
    ) -> str | None:
        if source.options.get("refresh_url"):
            return str(source.options["refresh_url"])
        account_id = source.options.get("account_id")
        if not account_id:
            return None
        api_base_env = str(
            source.options.get("refresh_api_base_env", "WERSS_API_BASE_URL")
        )
        api_base = os.environ.get(api_base_env)
        if not api_base:
            parsed = urllib.parse.urlsplit(feed_url)
            if parsed.scheme and parsed.netloc:
                api_base = f"{parsed.scheme}://{parsed.netloc}/api/v1/wx"
        if not api_base:
            return None
        return f"{api_base.rstrip('/')}/mps/update/{account_id}"

    @staticmethod
    def _refresh_headers(source: SourceConfig) -> dict[str, str] | None:
        bearer_env = str(
            source.options.get("werss_bearer_token_env", "WERSS_BEARER_TOKEN")
        )
        bearer = os.environ.get(bearer_env)
        if bearer:
            return {
                "Accept": "application/json",
                "Authorization": f"Bearer {bearer}",
            }
        key_env = str(
            source.options.get("werss_access_key_env", "WERSS_ACCESS_KEY")
        )
        secret_env = str(
            source.options.get("werss_secret_key_env", "WERSS_SECRET_KEY")
        )
        access_key = os.environ.get(key_env)
        secret_key = os.environ.get(secret_env)
        if access_key and secret_key:
            return {
                "Accept": "application/json",
                "Authorization": f"AK-SK {access_key}:{secret_key}",
            }
        return None

    @staticmethod
    def _is_stale(
        batch: CollectionBatch,
        source: SourceConfig,
        window: CollectionWindow,
    ) -> bool:
        if batch.stats.get("health_status") == "empty_feed":
            return True
        if not batch.next_cursor:
            return True
        try:
            latest = datetime.fromisoformat(
                batch.next_cursor.replace("Z", "+00:00")
            )
        except ValueError:
            return True
        if latest.tzinfo is None:
            latest = latest.replace(tzinfo=timezone.utc)
        freshness_hours = max(
            1.0, float(source.options.get("freshness_hours", 72))
        )
        return latest < window.end - timedelta(hours=freshness_hours)

    @staticmethod
    def _with_refresh_error(
        batch: CollectionBatch,
        error: CollectionError,
    ) -> CollectionBatch:
        status = BatchStatus.PARTIAL if batch.documents else BatchStatus.BLOCKED
        stats = dict(batch.stats)
        stats["health_status"] = error.code
        stats["requires_human_action"] = 1
        return replace(
            batch,
            status=status,
            errors=tuple(batch.errors) + (error,),
            stats=stats,
        )

    @staticmethod
    def _headers(source: SourceConfig) -> dict[str, str]:
        headers = {
            "Accept": "application/rss+xml, application/atom+xml, application/xml",
            "User-Agent": str(
                source.options.get("user_agent", "weekly-intel/0.1")
            ),
        }
        token_env = str(
            source.options.get(
                "auth_token_env", "WECHAT_FEED_AUTH_TOKEN"
            )
        )
        token = os.environ.get(token_env)
        if token:
            header_name = str(
                source.options.get("auth_header_name", "Authorization")
            )
            scheme = str(source.options.get("auth_scheme", "Bearer")).strip()
            headers[header_name] = f"{scheme} {token}".strip()
        return headers

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
        feed_entries = len(entries)
        if documents:
            status = BatchStatus.OK
            health_status = "ok"
            errors = ()
        elif feed_entries:
            status = BatchStatus.UNCHANGED
            health_status = "no_recent_update"
            errors = ()
        else:
            status = BatchStatus.PARTIAL
            health_status = "empty_feed"
            errors = (
                CollectionError(
                    code="empty_feed",
                    message="Feed is reachable but contains no entries",
                    retryable=True,
                    target=source.source_id,
                ),
            )
        return CollectionBatch(
            run_id=run_id,
            source_id=source.source_id,
            status=status,
            documents=documents,
            next_cursor=isoformat(latest_seen),
            errors=errors,
            stats={
                "feed_entries": feed_entries,
                "in_window": len(documents),
                "health_status": health_status,
            },
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
                stats={"health_status": "not_configured"},
            )
        try:
            payload = self._fetcher(
                feed_url,
                self._headers(source),
                float(source.options.get("timeout_seconds", 30)),
            )
            batch = self.parse(payload, source, window, run_id)
            if not source.options.get("refresh_before_collect", False):
                return batch
            if not self._is_stale(batch, source, window):
                return batch
            refresh_url = self._refresh_url(source, feed_url)
            dashboard_url = str(
                source.options.get(
                    "werss_dashboard_url",
                    urllib.parse.urlunsplit(
                        (*urllib.parse.urlsplit(feed_url)[:2], "/", "", "")
                    ),
                )
            )
            refresh_headers = self._refresh_headers(source)
            if not refresh_url or not refresh_headers:
                return self._with_refresh_error(
                    batch,
                    CollectionError(
                        code="werss_refresh_credentials_required",
                        message=(
                            "WeRSS feed is stale; configure WERSS_ACCESS_KEY and "
                            "WERSS_SECRET_KEY (or WERSS_BEARER_TOKEN) to refresh it"
                        ),
                        retryable=False,
                        target=dashboard_url,
                        details={"requires_human_verification": True},
                    ),
                )
            try:
                refresh_payload = self._fetcher(
                    refresh_url,
                    refresh_headers,
                    float(source.options.get("refresh_timeout_seconds", 30)),
                )
                response = json.loads(refresh_payload.decode("utf-8"))
                if response.get("code", 0) != 0:
                    raise RuntimeError(
                        str(response.get("message") or "WeRSS refresh rejected")
                    )
                self._sleeper(
                    max(0.0, float(source.options.get("refresh_wait_seconds", 5)))
                )
                refreshed_payload = self._fetcher(
                    feed_url,
                    self._headers(source),
                    float(source.options.get("timeout_seconds", 30)),
                )
                refreshed = self.parse(
                    refreshed_payload, source, window, run_id
                )
                if not self._is_stale(refreshed, source, window):
                    stats = dict(refreshed.stats)
                    stats["refresh_triggered"] = 1
                    return replace(refreshed, stats=stats)
                return self._with_refresh_error(
                    refreshed,
                    CollectionError(
                        code="wechat_login_or_verification_required",
                        message=(
                            "WeRSS accepted the refresh, but the feed stayed stale; "
                            "open WeRSS and complete WeChat QR login/verification"
                        ),
                        retryable=True,
                        target=dashboard_url,
                        details={"requires_human_verification": True},
                    ),
                )
            except urllib.error.HTTPError as error:
                return self._with_refresh_error(
                    batch,
                    CollectionError(
                        code=(
                            "werss_refresh_auth_failed"
                            if error.code in {401, 403}
                            else "werss_refresh_http_error"
                        ),
                        message=f"WeRSS refresh HTTP {error.code}",
                        retryable=error.code not in {401, 403},
                        target=dashboard_url,
                        details={
                            "http_status": error.code,
                            "requires_human_verification": error.code in {401, 403},
                        },
                    ),
                )
            except Exception as error:
                return self._with_refresh_error(
                    batch,
                    CollectionError(
                        code="werss_refresh_failed",
                        message=f"WeRSS refresh failed: {error}",
                        retryable=True,
                        target=dashboard_url,
                        details={"requires_human_verification": True},
                    ),
                )
        except urllib.error.HTTPError as error:
            if error.code in {401, 403}:
                status = BatchStatus.BLOCKED
                code = "feed_auth_failed"
                health_status = "auth_failed"
                retryable = False
            elif error.code == 429:
                status = BatchStatus.PARTIAL
                code = "feed_rate_limited"
                health_status = "rate_limited"
                retryable = True
            else:
                status = BatchStatus.ERROR
                code = "feed_upstream_error"
                health_status = "upstream_error"
                retryable = error.code >= 500
            return CollectionBatch(
                run_id=run_id,
                source_id=source.source_id,
                status=status,
                errors=(
                    CollectionError(
                        code=code,
                        message=f"Feed HTTP {error.code}",
                        retryable=retryable,
                        target=source.source_id,
                        details={"http_status": error.code},
                    ),
                ),
                stats={"health_status": health_status},
            )
        except ET.ParseError as error:
            return CollectionBatch(
                run_id=run_id,
                source_id=source.source_id,
                status=BatchStatus.ERROR,
                errors=(
                    CollectionError(
                        code="invalid_feed",
                        message=f"Feed XML is invalid: {error}",
                        retryable=True,
                        target=source.source_id,
                    ),
                ),
                stats={"health_status": "invalid_feed"},
            )
        except (urllib.error.URLError, TimeoutError) as error:
            reason = getattr(error, "reason", error)
            return CollectionBatch(
                run_id=run_id,
                source_id=source.source_id,
                status=BatchStatus.ERROR,
                errors=(
                    CollectionError(
                        code="feed_network_error",
                        message=f"Feed network error: {reason}",
                        retryable=True,
                        target=source.source_id,
                    ),
                ),
                stats={"health_status": "network_error"},
            )
        except Exception as error:
            return CollectionBatch(
                run_id=run_id,
                source_id=source.source_id,
                status=BatchStatus.ERROR,
                errors=(
                    CollectionError(
                        code="feed_unexpected_error",
                        message=f"{type(error).__name__}: {error}",
                        retryable=True,
                        target=source.source_id,
                    ),
                ),
                stats={"health_status": "unexpected_error"},
            )
