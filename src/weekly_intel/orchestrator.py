from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from .config import load_sources
from .contracts import CollectionBatch, CollectionWindow
from .db import Database
from .service import CollectionService
from .site_export import SiteDataExportAgent
from .weekly import WeeklyBuildResult, WeeklyPipelineService


@dataclass(frozen=True, slots=True)
class AutomatedRunResult:
    status: str
    collection: tuple[dict[str, Any], ...]
    weekly: WeeklyBuildResult
    audit_path: Path
    site_data_path: Path | None


class WeeklyOrchestrator:
    def __init__(
        self,
        database: Database,
        sources_path: Path,
        department: dict[str, Any],
    ):
        self.database = database
        self.sources = load_sources(sources_path)
        self.department = department

    @staticmethod
    def _batch_summary(batch: CollectionBatch) -> dict[str, Any]:
        return {
            "source_id": batch.source_id,
            "run_id": batch.run_id,
            "status": batch.status.value,
            "documents": len(batch.documents),
            "errors": [asdict(error) for error in batch.errors],
            "stats": dict(batch.stats),
        }

    def run(
        self,
        end: datetime,
        days: int,
        iso_week: str,
        output_path: Path,
        audit_directory: Path,
        site_data_path: Path | None = None,
    ) -> AutomatedRunResult:
        if end.tzinfo is None:
            raise ValueError("end must be timezone-aware")
        window = CollectionWindow(end - timedelta(days=days), end)
        service = CollectionService(self.database)
        batches: list[CollectionBatch] = []
        batches.append(
            service.collect_arxiv(self.sources["arxiv"], window, limit=200)
        )
        batches.append(
            service.collect_openreview(
                self.sources["openreview"],
                window,
                page_size=500,
                max_pages=10,
            )
        )
        batches.append(
            service.collect_crossref(
                self.sources["crossref"],
                window,
                rows_per_query=50,
            )
        )
        for source in self.sources.values():
            if source.enabled and source.connector == "GitHubCollector":
                batches.append(service.collect_github(source, window, per_page=100))
        batches.append(
            service.collect_huggingface(
                self.sources["huggingface_hub"],
                window,
                limit_per_query=20,
            )
        )
        for source in self.sources.values():
            if source.enabled and source.connector == "WechatPoolCollector":
                batches.append(service.collect_wechat(source, window))
        batches.append(
            service.collect_venues(self.sources["venue_official_pages"], window)
        )
        batches.append(
            service.collect_manual(self.sources["manual_inbox"], window)
        )
        weekly = WeeklyPipelineService(
            self.database, self.department
        ).build(iso_week, window.start, window.end, output_path)
        exported_site_data: Path | None = None
        if site_data_path is not None:
            with self.database.transaction() as connection:
                exported_site_data = SiteDataExportAgent().export(
                    connection, weekly.issue_id, site_data_path
                )
        collection = tuple(self._batch_summary(batch) for batch in batches)
        failed = [
            item
            for item in collection
            if item["status"] in {"blocked", "error"}
        ]
        status = "degraded" if failed else "ok"
        audit_directory.mkdir(parents=True, exist_ok=True)
        audit_path = audit_directory / (
            end.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + ".json"
        )
        payload = {
            "status": status,
            "started_for": end.isoformat(),
            "window": {
                "start": window.start.isoformat(),
                "end": window.end.isoformat(),
            },
            "collection": collection,
            "weekly": {
                "issue_id": weekly.issue_id,
                "assessed_count": weekly.assessed_count,
                "trend_count": weekly.trend_count,
                "selection_count": weekly.selection_count,
                "estimated_read_minutes": weekly.estimated_read_minutes,
                "output_path": str(weekly.output_path),
                "version_diffs": weekly.version_diffs,
                "interpretation_claims": weekly.interpretation_claims,
                "interpretation_links": weekly.interpretation_links,
                "deep_reads": weekly.deep_reads,
                "paper_contents_fetched": weekly.paper_contents_fetched,
                "paper_contents_failed": weekly.paper_contents_failed,
                "site_data_path": (
                    str(exported_site_data) if exported_site_data else None
                ),
            },
        }
        audit_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return AutomatedRunResult(
            status=status,
            collection=collection,
            weekly=weekly,
            audit_path=audit_path.resolve(),
            site_data_path=exported_site_data,
        )
