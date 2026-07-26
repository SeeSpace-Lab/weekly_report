from __future__ import annotations

import html
import json
import os
import re
import subprocess
import urllib.error
import urllib.request
import uuid
import xml.etree.ElementTree as ET
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


def _authentication_token(source: SourceConfig) -> str | None:
    """Resolve GitHub credentials without persisting a token in the project."""
    token_env = str(source.options.get("token_env", "GITHUB_TOKEN"))
    for variable in (token_env, "GH_TOKEN"):
        token = os.environ.get(variable)
        if token:
            return token.strip()
    try:
        result = subprocess.run(
            ["gh", "auth", "token", "--hostname", "github.com"],
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=5,
        )
    except (FileNotFoundError, subprocess.SubprocessError):
        return None
    return result.stdout.strip() if result.returncode == 0 else None


def _datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(
        timezone.utc
    )


class GitHubCollector:
    name = "GitHubCollector"

    def __init__(
        self,
        fetcher: Callable[[str, dict[str, str], float], bytes] | None = None,
    ):
        self._custom_fetcher = fetcher is not None
        self._fetcher = fetcher or self._fetch

    @staticmethod
    def _fetch(url: str, headers: dict[str, str], timeout: float) -> bytes:
        request = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.read()

    def parse_atom(
        self,
        payload: bytes,
        source: SourceConfig,
        repository: str,
        window: CollectionWindow,
        run_id: str,
    ) -> CollectionBatch:
        namespace = {"atom": "http://www.w3.org/2005/Atom"}
        root = ET.fromstring(payload)
        documents: list[CollectedDocument] = []
        latest_seen: datetime | None = None
        entries = root.findall("atom:entry", namespace)
        for entry in entries:
            updated = _datetime(entry.findtext("atom:updated", namespaces=namespace))
            if updated:
                latest_seen = max(latest_seen or updated, updated)
            if not updated or not (window.start <= updated <= window.end):
                continue
            link = next(
                (
                    node.attrib.get("href")
                    for node in entry.findall("atom:link", namespace)
                    if node.attrib.get("rel", "alternate") == "alternate"
                ),
                None,
            )
            entry_id = entry.findtext("atom:id", default="", namespaces=namespace)
            name = entry.findtext(
                "atom:title", default=entry_id, namespaces=namespace
            ).strip()
            content = entry.findtext(
                "atom:content", default="", namespaces=namespace
            )
            summary = html.unescape(re.sub(r"<[^>]+>", " ", content))
            summary = re.sub(r"\s+", " ", summary).strip()
            version = (
                link.rsplit("/tag/", 1)[-1]
                if link and "/tag/" in link
                else name
            )
            author = entry.findtext(
                "atom:author/atom:name", default="", namespaces=namespace
            )
            raw_payload = {
                "id": entry_id,
                "title": name,
                "updated": isoformat(updated),
                "url": link,
                "version": version,
                "summary": summary,
            }
            documents.append(
                CollectedDocument(
                    source_id=source.source_id,
                    external_id=entry_id or version,
                    document_type=DocumentType.RELEASE,
                    canonical_url=link,
                    title=f"{repository} {name}",
                    published_at=updated,
                    updated_at_source=updated,
                    discovered_at=utc_now(),
                    authors=(author,) if author else (),
                    summary=summary or None,
                    language="en",
                    identifiers={"github": repository.casefold()},
                    metadata={
                        "item_title": repository,
                        "repository": repository,
                        "version": version,
                        "prerelease": False,
                        "draft": False,
                        "assets": 0,
                        "transport": "atom",
                    },
                    raw_payload=raw_payload,
                    content_hash=sha256_text(json_dumps(raw_payload)),
                )
            )
        return CollectionBatch(
            run_id=run_id,
            source_id=source.source_id,
            status=BatchStatus.OK if documents else BatchStatus.UNCHANGED,
            documents=documents,
            next_cursor=isoformat(latest_seen),
            stats={
                "fetched": len(entries),
                "in_window": len(documents),
                "transport": "atom",
            },
        )

    def collect(
        self,
        source: SourceConfig,
        window: CollectionWindow,
        cursor: str | None = None,
    ) -> CollectionBatch:
        run_id = str(uuid.uuid4())
        repository = str(source.options.get("repository", ""))
        if not repository:
            return CollectionBatch(
                run_id=run_id,
                source_id=source.source_id,
                status=BatchStatus.ERROR,
                errors=(
                    CollectionError(
                        code="invalid_config",
                        message="GitHub source requires repository",
                        retryable=False,
                    ),
                ),
            )
        endpoint = str(
            source.options.get("api_endpoint", "https://api.github.com")
        ).rstrip("/")
        per_page = int(source.options.get("per_page", 100))
        url = f"{endpoint}/repos/{repository}/releases?per_page={per_page}"
        headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": str(
                source.options.get("user_agent", "weekly-intel/0.1")
            ),
            "X-GitHub-Api-Version": "2022-11-28",
        }
        token = _authentication_token(source)
        if token:
            headers["Authorization"] = f"Bearer {token}"
        try:
            if not token and not self._custom_fetcher:
                atom_url = f"https://github.com/{repository}/releases.atom"
                atom_payload = self._fetcher(
                    atom_url,
                    {
                        "Accept": "application/atom+xml",
                        "User-Agent": headers["User-Agent"],
                    },
                    float(source.options.get("timeout_seconds", 30)),
                )
                return self.parse_atom(
                    atom_payload, source, repository, window, run_id
                )
            payload = self._fetcher(
                url, headers, float(source.options.get("timeout_seconds", 30))
            )
            releases = json.loads(payload.decode("utf-8"))
            documents = []
            latest_seen = None
            for release in releases:
                published = _datetime(release.get("published_at"))
                updated = _datetime(release.get("updated_at"))
                event_time = updated or published
                if event_time:
                    latest_seen = max(latest_seen or event_time, event_time)
                if not event_time or not (window.start <= event_time <= window.end):
                    continue
                tag = release.get("tag_name") or str(release.get("id"))
                name = release.get("name") or tag
                raw_payload = dict(release)
                documents.append(
                    CollectedDocument(
                        source_id=source.source_id,
                        external_id=str(release.get("id") or tag),
                        document_type=DocumentType.RELEASE,
                        canonical_url=release.get("html_url"),
                        title=f"{repository} {name}",
                        published_at=published,
                        updated_at_source=updated,
                        discovered_at=utc_now(),
                        authors=(
                            str((release.get("author") or {}).get("login", "")),
                        ),
                        summary=release.get("body") or None,
                        language="en",
                        identifiers={"github": repository.casefold()},
                        metadata={
                            "item_title": repository,
                            "repository": repository,
                            "version": tag,
                            "prerelease": bool(release.get("prerelease")),
                            "draft": bool(release.get("draft")),
                            "assets": len(release.get("assets") or []),
                        },
                        raw_payload=raw_payload,
                        content_hash=sha256_text(json_dumps(raw_payload)),
                    )
                )
            return CollectionBatch(
                run_id=run_id,
                source_id=source.source_id,
                status=BatchStatus.OK if documents else BatchStatus.UNCHANGED,
                documents=documents,
                next_cursor=isoformat(latest_seen),
                stats={"fetched": len(releases), "in_window": len(documents)},
            )
        except urllib.error.HTTPError as error:
            rate_limited = error.code in {403, 429}
            return CollectionBatch(
                run_id=run_id,
                source_id=source.source_id,
                status=BatchStatus.BLOCKED if rate_limited else BatchStatus.ERROR,
                errors=(
                    CollectionError(
                        code="rate_limited" if rate_limited else "http_error",
                        message=f"GitHub HTTP {error.code}",
                        retryable=True,
                        target=url,
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
                        target=url,
                    ),
                ),
            )
