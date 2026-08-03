from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from .config import department_source_configs, load_sources
from .contracts import CollectionBatch, CollectionWindow
from .db import Database
from .service import CollectionService
from .site_export import SiteDataExportAgent
from .weekly import WeeklyBuildResult, WeeklyPipelineService


@dataclass(frozen=True, slots=True)
class AutomatedRunResult:
    status: str
    collection: tuple[dict[str, Any], ...]
    human_actions: tuple[dict[str, Any], ...]
    weekly: WeeklyBuildResult
    audit_path: Path
    site_data_path: Path | None


class WeeklyOrchestrator:
    def __init__(
        self,
        database: Database,
        sources_path: Path,
        department: dict[str, Any],
        excluded_connectors: set[str] | None = None,
    ):
        self.database = database
        self.sources = department_source_configs(
            load_sources(sources_path),
            department,
        )
        self.department = department
        self.excluded_connectors = frozenset(excluded_connectors or ())

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
        window_start: datetime | None = None,
    ) -> AutomatedRunResult:
        if end.tzinfo is None:
            raise ValueError("end must be timezone-aware")
        start = window_start or end - timedelta(days=days)
        window = CollectionWindow(start, end)
        service = CollectionService(self.database)
        batches: list[CollectionBatch] = []
        for source in self.sources.values():
            if not source.enabled:
                continue
            if source.connector in self.excluded_connectors:
                continue
            if source.connector == "ArxivCollector":
                batches.append(
                    service.collect_arxiv(
                        source,
                        window,
                        limit=int(source.options.get("max_results", 200)),
                    )
                )
            elif source.connector == "OpenReviewCollector":
                batches.append(
                    service.collect_openreview(
                        source,
                        window,
                        page_size=int(source.options.get("page_size", 100)),
                        max_pages=int(source.options.get("max_pages", 3)),
                    )
                )
            elif source.connector == "CrossrefCollector":
                batches.append(
                    service.collect_crossref(
                        source,
                        window,
                        rows_per_query=int(
                            source.options.get("rows_per_query", 50)
                        ),
                    )
                )
            elif source.connector == "GitHubCollector":
                batches.append(
                    service.collect_github(source, window, per_page=100)
                )
            elif source.connector == "HuggingFaceCollector":
                batches.append(
                    service.collect_huggingface(
                        source,
                        window,
                        limit_per_query=int(
                            source.options.get("limit_per_query", 20)
                        ),
                    )
                )
            elif source.connector == "WechatPoolCollector":
                batches.append(service.collect_wechat(source, window))
            elif source.connector == "VenueCollector":
                batches.append(service.collect_venues(source, window))
            elif source.connector == "ManualInboxCollector":
                batches.append(service.collect_manual(source, window))
            else:
                raise ValueError(
                    f"unsupported collector for {source.source_id}: "
                    f"{source.connector}"
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
        unhealthy = [
            item
            for item in collection
            if item["status"] in {"partial", "blocked", "error"}
        ]
        human_action_codes = {
            "challenge_required",
            "werss_refresh_credentials_required",
            "werss_refresh_auth_failed",
            "wechat_login_or_verification_required",
        }
        human_actions = tuple(
            {
                "source_id": item["source_id"],
                "code": error["code"],
                "message": error["message"],
                "target": error.get("target"),
            }
            for item in collection
            for error in item["errors"]
            if error["code"] in human_action_codes
            or error.get("details", {}).get("requires_human_verification")
        )
        if human_actions:
            status = "needs_attention"
        else:
            status = "degraded" if unhealthy else "ok"
        audit_directory.mkdir(parents=True, exist_ok=True)
        audit_path = audit_directory / (
            f"{self.department['department_id']}-"
            + end.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            + ".json"
        )
        payload = {
            "status": status,
            "started_for": end.isoformat(),
            "window": {
                "start": window.start.isoformat(),
                "end": window.end.isoformat(),
            },
            "collection": collection,
            "human_actions": human_actions,
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
            human_actions=human_actions,
            weekly=weekly,
            audit_path=audit_path.resolve(),
            site_data_path=exported_site_data,
        )
