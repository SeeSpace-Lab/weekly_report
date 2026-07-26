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
    CollectionBatch,
    CollectionError,
    CollectionWindow,
    CollectedDocument,
    DocumentType,
    SourceConfig,
)
from ..utils import isoformat, json_dumps, sha256_text, utc_now


def _datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(
        timezone.utc
    )


class HuggingFaceCollector:
    name = "HuggingFaceCollector"

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

    def _url(
        self,
        endpoint: str,
        resource_type: str,
        search: str,
        limit: int,
    ) -> str:
        params = urllib.parse.urlencode(
            {
                "search": search,
                "sort": "lastModified",
                "direction": "-1",
                "limit": str(limit),
                "full": "true",
            }
        )
        return f"{endpoint.rstrip('/')}/api/{resource_type}?{params}"

    def _document(
        self,
        source: SourceConfig,
        resource_type: str,
        record: dict[str, Any],
        discovered_at: datetime,
    ) -> CollectedDocument | None:
        repo_id = record.get("id") or record.get("modelId")
        if not repo_id:
            return None
        modified = _datetime(record.get("lastModified"))
        created = _datetime(record.get("createdAt"))
        sha = record.get("sha") or "unknown"
        tags = record.get("tags") or []
        card = record.get("cardData") or {}
        summary = (
            card.get("summary")
            or card.get("description")
            or f"Tags: {', '.join(str(tag) for tag in tags[:20])}"
        )
        document_type = (
            DocumentType.DATASET
            if resource_type == "datasets"
            else DocumentType.MODEL
        )
        url_segment = "datasets/" if resource_type == "datasets" else ""
        payload = dict(record)
        return CollectedDocument(
            source_id=source.source_id,
            external_id=f"{resource_type}:{repo_id}:{sha}",
            document_type=document_type,
            canonical_url=f"https://huggingface.co/{url_segment}{repo_id}",
            title=str(repo_id),
            published_at=created,
            updated_at_source=modified,
            discovered_at=discovered_at,
            authors=(str(record.get("author") or str(repo_id).split("/", 1)[0]),),
            summary=str(summary),
            language="en",
            identifiers={"huggingface": f"{resource_type}:{str(repo_id).casefold()}"},
            metadata={
                "item_title": repo_id,
                "repo_id": repo_id,
                "resource_type": resource_type,
                "version": sha,
                "downloads": record.get("downloads"),
                "likes": record.get("likes"),
                "trending_score": record.get("trendingScore"),
                "pipeline_tag": record.get("pipeline_tag"),
                "tags": tags,
                "gated": record.get("gated"),
                "private": record.get("private", False),
                "card_data": card,
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
        endpoint = str(source.options.get("endpoint", "https://huggingface.co"))
        searches = source.options.get(
            "search_terms", ["llm inference", "kv cache", "llm serving"]
        )
        resource_types = source.options.get(
            "resource_types", ["models", "datasets"]
        )
        limit = int(source.options.get("limit_per_query", 20))
        timeout = float(source.options.get("timeout_seconds", 30))
        headers = {
            "Accept": "application/json",
            "User-Agent": str(
                source.options.get("user_agent", "weekly-intel/0.1")
            ),
        }
        token_env = source.options.get("token_env", "HF_TOKEN")
        token = os.environ.get(str(token_env))
        if token:
            headers["Authorization"] = f"Bearer {token}"
        documents: dict[str, CollectedDocument] = {}
        errors: list[CollectionError] = []
        fetched = 0
        latest_seen = None
        discovered_at = utc_now()
        for resource_type in resource_types:
            for search in searches:
                url = self._url(endpoint, str(resource_type), str(search), limit)
                try:
                    payload = self._fetcher(url, headers, timeout)
                    records = json.loads(payload.decode("utf-8"))
                    fetched += len(records)
                    for record in records:
                        document = self._document(
                            source, str(resource_type), record, discovered_at
                        )
                        if document is None:
                            continue
                        event_time = (
                            document.updated_at_source or document.published_at
                        )
                        if event_time:
                            latest_seen = max(latest_seen or event_time, event_time)
                        if event_time and window.start <= event_time <= window.end:
                            documents[document.idempotency_key] = document
                except urllib.error.HTTPError as error:
                    errors.append(
                        CollectionError(
                            code=(
                                "rate_limited"
                                if error.code in {403, 429}
                                else "http_error"
                            ),
                            message=f"Hugging Face HTTP {error.code}",
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
            status = BatchStatus.BLOCKED if all(
                error.code == "rate_limited" for error in errors
            ) else BatchStatus.ERROR
        elif result:
            status = BatchStatus.OK
        else:
            status = BatchStatus.UNCHANGED
        return CollectionBatch(
            run_id=run_id,
            source_id=source.source_id,
            status=status,
            documents=result,
            next_cursor=isoformat(latest_seen),
            errors=tuple(errors),
            stats={
                "queries": len(resource_types) * len(searches),
                "fetched": fetched,
                "deduplicated_in_window": len(result),
            },
        )
