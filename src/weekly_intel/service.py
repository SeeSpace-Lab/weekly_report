from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from .collectors import (
    ArxivCollector,
    CrossrefCollector,
    GitHubCollector,
    HuggingFaceCollector,
    ManualInboxCollector,
    OpenReviewCollector,
    WechatPoolCollector,
    VenueCollector,
)
from .contracts import CollectionBatch, CollectionWindow, Collector, SourceConfig
from .db import Database
from .repository import Repository


class CollectionService:
    def __init__(self, database: Database):
        self.database = database

    def _run(
        self,
        collector: Collector,
        source: SourceConfig,
        window: CollectionWindow,
    ) -> CollectionBatch:
        with self.database.transaction() as connection:
            repository = Repository(connection)
            repository.upsert_source(source)
            cursor = repository.get_cursor(source.source_id)
        batch = collector.collect(source, window, cursor)
        with self.database.transaction() as connection:
            repository = Repository(connection)
            repository.start_run(
                batch.run_id, source, window, cursor, collector.name
            )
            created, skipped = repository.ingest_documents(
                batch.run_id, batch.documents
            )
            repository.finish_run(batch, created, skipped)
        return batch

    def collect_arxiv(
        self,
        source: SourceConfig,
        window: CollectionWindow,
        limit: int | None = None,
    ) -> CollectionBatch:
        if limit is not None:
            source = replace(
                source, options={**source.options, "max_results": limit}
            )
        collector = ArxivCollector()
        return self._run(collector, source, window)

    def collect_openreview(
        self,
        source: SourceConfig,
        window: CollectionWindow,
        page_size: int | None = None,
        max_pages: int | None = None,
    ) -> CollectionBatch:
        options = dict(source.options)
        if page_size is not None:
            options["page_size"] = page_size
        if max_pages is not None:
            options["max_pages"] = max_pages
        source = replace(source, options=options)
        return self._run(OpenReviewCollector(), source, window)

    def collect_crossref(
        self,
        source: SourceConfig,
        window: CollectionWindow,
        rows_per_query: int | None = None,
    ) -> CollectionBatch:
        if rows_per_query is not None:
            source = replace(
                source,
                options={
                    **source.options,
                    "rows_per_query": rows_per_query,
                },
            )
        return self._run(CrossrefCollector(), source, window)

    def collect_github(
        self,
        source: SourceConfig,
        window: CollectionWindow,
        per_page: int | None = None,
    ) -> CollectionBatch:
        if per_page is not None:
            source = replace(
                source, options={**source.options, "per_page": per_page}
            )
        return self._run(GitHubCollector(), source, window)

    def collect_manual(
        self,
        source: SourceConfig,
        window: CollectionWindow,
        inbox_path: Path | None = None,
    ) -> CollectionBatch:
        if inbox_path is not None:
            source = replace(
                source, options={**source.options, "inbox_path": str(inbox_path)}
            )
        return self._run(ManualInboxCollector(), source, window)

    def collect_huggingface(
        self,
        source: SourceConfig,
        window: CollectionWindow,
        limit_per_query: int | None = None,
    ) -> CollectionBatch:
        if limit_per_query is not None:
            source = replace(
                source,
                options={
                    **source.options,
                    "limit_per_query": limit_per_query,
                },
            )
        return self._run(HuggingFaceCollector(), source, window)

    def collect_wechat(
        self,
        source: SourceConfig,
        window: CollectionWindow,
    ) -> CollectionBatch:
        return self._run(WechatPoolCollector(), source, window)

    def collect_venues(
        self,
        source: SourceConfig,
        window: CollectionWindow,
    ) -> CollectionBatch:
        return self._run(VenueCollector(), source, window)
