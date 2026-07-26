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


def _value(content: dict[str, Any], key: str, default: Any = None) -> Any:
    result = content.get(key, default)
    if isinstance(result, dict) and "value" in result:
        return result["value"]
    return result


def _milliseconds(value: Any) -> datetime | None:
    if value is None:
        return None
    try:
        return datetime.fromtimestamp(int(value) / 1000, tz=timezone.utc)
    except (TypeError, ValueError, OSError):
        return None


class OpenReviewBlockedError(RuntimeError):
    def __init__(self, message: str, challenge_url: str | None = None):
        super().__init__(message)
        self.challenge_url = challenge_url


class OpenReviewCollector:
    name = "OpenReviewCollector"

    def __init__(
        self,
        fetcher: Callable[[str, dict[str, str], float], bytes] | None = None,
    ):
        self._fetcher = fetcher or self._fetch

    @staticmethod
    def _fetch(url: str, headers: dict[str, str], timeout: float) -> bytes:
        request = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return response.read()
        except urllib.error.HTTPError as error:
            payload = error.read()
            if error.code == 403:
                try:
                    body = json.loads(payload.decode("utf-8"))
                except (json.JSONDecodeError, UnicodeDecodeError):
                    body = {}
                if body.get("name") == "ChallengeRequiredError":
                    details = body.get("details") or {}
                    raise OpenReviewBlockedError(
                        body.get("message", "OpenReview challenge required"),
                        details.get("challengeUrl"),
                    ) from error
            raise

    def build_url(
        self,
        source: SourceConfig,
        venue_id: str,
        offset: int,
        limit: int,
    ) -> str:
        endpoint = str(source.options.get("api_v2", "https://api2.openreview.net"))
        params = {
            "content.venueid": venue_id,
            "limit": str(limit),
            "offset": str(offset),
        }
        return f"{endpoint.rstrip('/')}/notes?{urllib.parse.urlencode(params)}"

    def parse_note(
        self,
        note: dict[str, Any],
        source: SourceConfig,
        venue_id: str,
        discovered_at: datetime,
    ) -> CollectedDocument | None:
        content = note.get("content") or {}
        note_id = note.get("id")
        title = str(_value(content, "title", "")).strip()
        if not note_id or not title:
            return None
        authors_value = _value(content, "authors", [])
        authors = (
            [str(author) for author in authors_value]
            if isinstance(authors_value, list)
            else [str(authors_value)]
        )
        published = _milliseconds(
            note.get("tcdate") or note.get("cdate") or note.get("pdate")
        )
        updated = _milliseconds(
            note.get("tmdate") or note.get("mdate") or note.get("tcdate")
        )
        forum_id = note.get("forum") or note_id
        venue = _value(content, "venue")
        resolved_venue_id = _value(content, "venueid", venue_id)
        keywords = _value(content, "keywords", [])
        pdf = _value(content, "pdf")
        doi = _value(content, "doi")
        arxiv_id = _value(content, "arxiv_id") or _value(content, "arxiv")
        identifiers = {"openreview_forum": str(forum_id)}
        if doi:
            identifiers["doi"] = str(doi).lower()
        if arxiv_id:
            identifiers["arxiv"] = str(arxiv_id).split("v", 1)[0]
        metadata = {
            "venue_id": resolved_venue_id,
            "venue_status": venue,
            "invitation": note.get("invitation"),
            "number": _value(content, "paper_number"),
            "keywords": keywords if isinstance(keywords, list) else [keywords],
            "pdf": pdf,
            "version": f"tmdate-{int((updated or published or discovered_at).timestamp())}",
            "api_version": 2,
        }
        raw_payload = {
            "id": note_id,
            "forum": forum_id,
            "cdate": note.get("cdate"),
            "mdate": note.get("mdate"),
            "tcdate": note.get("tcdate"),
            "tmdate": note.get("tmdate"),
            "content": content,
            "invitation": note.get("invitation"),
        }
        return CollectedDocument(
            source_id=source.source_id,
            external_id=str(note_id),
            document_type=DocumentType.PAPER_RECORD,
            canonical_url=f"https://openreview.net/forum?id={forum_id}",
            title=title,
            published_at=published,
            updated_at_source=updated,
            discovered_at=discovered_at,
            authors=authors,
            summary=str(_value(content, "abstract", "")).strip() or None,
            language="en",
            identifiers=identifiers,
            metadata=metadata,
            raw_payload=raw_payload,
            content_hash=sha256_text(json_dumps(raw_payload)),
        )

    def collect(
        self,
        source: SourceConfig,
        window: CollectionWindow,
        cursor: str | None = None,
    ) -> CollectionBatch:
        run_id = str(uuid.uuid4())
        venues = source.options.get("venues", [])
        page_size = int(source.options.get("page_size", 500))
        max_pages = int(source.options.get("max_pages", 10))
        timeout = float(source.options.get("timeout_seconds", 30))
        headers = {
            "User-Agent": str(
                source.options.get(
                    "user_agent", "weekly-intel/0.1 research survey"
                )
            ),
            "Accept": "application/json",
        }
        token_env = source.options.get("token_env")
        token = os.environ.get(str(token_env)) if token_env else None
        if token:
            headers["Authorization"] = f"Bearer {token}"
        discovered_at = utc_now()
        documents: list[CollectedDocument] = []
        errors: list[CollectionError] = []
        latest_seen: datetime | None = None
        fetched = 0
        try:
            for venue in venues:
                venue_id = venue["venue_id"] if isinstance(venue, dict) else str(venue)
                for page in range(max_pages):
                    url = self.build_url(
                        source, venue_id, page * page_size, page_size
                    )
                    payload = self._fetcher(url, headers, timeout)
                    body = json.loads(payload.decode("utf-8"))
                    notes = body.get("notes", [])
                    fetched += len(notes)
                    for note in notes:
                        document = self.parse_note(
                            note, source, venue_id, discovered_at
                        )
                        if document is None:
                            continue
                        event_time = (
                            document.updated_at_source or document.published_at
                        )
                        if event_time:
                            latest_seen = max(latest_seen or event_time, event_time)
                        if event_time and window.start <= event_time <= window.end:
                            documents.append(document)
                    if len(notes) < page_size:
                        break
        except OpenReviewBlockedError as error:
            errors.append(
                CollectionError(
                    code="challenge_required",
                    message=str(error),
                    retryable=True,
                    target=error.challenge_url,
                )
            )
            status = BatchStatus.PARTIAL if documents else BatchStatus.BLOCKED
        except Exception as error:
            errors.append(
                CollectionError(
                    code=type(error).__name__,
                    message=str(error),
                    retryable=True,
                    target=str(source.options.get("api_v2", "")),
                )
            )
            status = BatchStatus.PARTIAL if documents else BatchStatus.ERROR
        else:
            status = BatchStatus.OK if documents else BatchStatus.UNCHANGED
        return CollectionBatch(
            run_id=run_id,
            source_id=source.source_id,
            status=status,
            documents=documents,
            next_cursor=isoformat(latest_seen),
            errors=errors,
            stats={
                "venues": len(venues),
                "fetched": fetched,
                "in_window": len(documents),
            },
        )
