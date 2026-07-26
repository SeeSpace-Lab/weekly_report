from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any, Mapping, Protocol, Sequence


class BatchStatus(StrEnum):
    OK = "ok"
    PARTIAL = "partial"
    BLOCKED = "blocked"
    ERROR = "error"
    UNCHANGED = "unchanged"


class DocumentType(StrEnum):
    PAPER_RECORD = "paper_record"
    PAPER_PDF = "paper_pdf"
    VENUE_EVENT = "venue_event"
    RELEASE = "release"
    REPOSITORY = "repository"
    MODEL = "model"
    DATASET = "dataset"
    BENCHMARK = "benchmark"
    REVIEW_ARTICLE = "review_article"
    OFFICIAL_BLOG = "official_blog"
    MANUAL = "manual"


@dataclass(frozen=True, slots=True)
class CollectionWindow:
    start: datetime
    end: datetime

    def __post_init__(self) -> None:
        if self.start.tzinfo is None or self.end.tzinfo is None:
            raise ValueError("CollectionWindow must use timezone-aware datetimes")
        if self.end < self.start:
            raise ValueError("CollectionWindow.end must not precede start")


@dataclass(frozen=True, slots=True)
class SourceConfig:
    source_id: str
    name: str
    source_type: str
    connector: str
    tier: str
    homepage_url: str | None = None
    enabled: bool = True
    options: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class CollectedDocument:
    source_id: str
    external_id: str | None
    document_type: DocumentType
    canonical_url: str | None
    title: str
    published_at: datetime | None
    discovered_at: datetime
    updated_at_source: datetime | None = None
    authors: Sequence[str] = ()
    summary: str | None = None
    content_text: str | None = None
    content_html: str | None = None
    language: str | None = None
    identifiers: Mapping[str, str] = field(default_factory=dict)
    metadata: Mapping[str, Any] = field(default_factory=dict)
    raw_payload: Mapping[str, Any] | None = None
    content_hash: str = ""

    def __post_init__(self) -> None:
        if not self.title.strip():
            raise ValueError("CollectedDocument.title must not be empty")
        if not self.external_id and not self.canonical_url:
            raise ValueError(
                "CollectedDocument requires external_id or canonical_url"
            )
        if self.discovered_at.tzinfo is None:
            raise ValueError("discovered_at must be timezone-aware")

    @property
    def idempotency_key(self) -> str:
        stable_value = self.external_id or self.canonical_url
        return f"{self.source_id}:{stable_value}"


@dataclass(frozen=True, slots=True)
class CollectionError:
    code: str
    message: str
    retryable: bool
    target: str | None = None
    details: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class CollectionBatch:
    run_id: str
    source_id: str
    status: BatchStatus
    documents: Sequence[CollectedDocument] = ()
    next_cursor: str | None = None
    errors: Sequence[CollectionError] = ()
    stats: Mapping[str, int | float | str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.status in {BatchStatus.BLOCKED, BatchStatus.ERROR} and not self.errors:
            raise ValueError(f"{self.status} batch must include at least one error")
        if self.status == BatchStatus.UNCHANGED and self.documents:
            raise ValueError("unchanged batch cannot contain documents")


class Collector(Protocol):
    name: str

    def collect(
        self,
        source: SourceConfig,
        window: CollectionWindow,
        cursor: str | None = None,
    ) -> CollectionBatch:
        """Collect raw documents without LLM-based relevance filtering."""

