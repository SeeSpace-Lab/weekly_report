from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import os
from pathlib import Path
from typing import Any

from .agents import (
    DepartmentAssessmentAgent,
    InterpretationLinkAgent,
    PaperDeepReadAgent,
    TrendClusteringAgent,
    VersionDiffAgent,
    WeeklySelectionAgent,
)
from .db import Database
from .analysis_backend import backend_from_environment
from .render import MarkdownRenderAgent
from .paper_content import PaperContentWorker


@dataclass(frozen=True, slots=True)
class WeeklyBuildResult:
    issue_id: str
    assessed_count: int
    trend_count: int
    selection_count: int
    estimated_read_minutes: float
    output_path: Path
    version_diffs: int = 0
    interpretation_claims: int = 0
    interpretation_links: int = 0
    deep_reads: int = 0
    paper_contents_fetched: int = 0
    paper_contents_failed: int = 0


class WeeklyPipelineService:
    def __init__(self, database: Database, department: dict[str, Any]):
        self.database = database
        self.department = department

    def build(
        self,
        iso_week: str,
        window_start: datetime,
        window_end: datetime,
        output_path: Path,
    ) -> WeeklyBuildResult:
        with self.database.transaction() as connection:
            version_diffs = VersionDiffAgent().run(connection)
            interpretation_claims, interpretation_links = (
                InterpretationLinkAgent().run(connection)
            )
            assessment_agent = DepartmentAssessmentAgent(self.department)
            assessed = assessment_agent.assess_window(
                connection, window_start, window_end
            )
            trend_agent = TrendClusteringAgent(self.department)
            trends = trend_agent.cluster(result for _, result in assessed)
            selection_agent = WeeklySelectionAgent(self.department)
            issue_id, selection_count, minutes = selection_agent.build_issue(
                connection,
                iso_week,
                window_start,
                window_end,
                assessed,
                trends,
            )
            content_run = None
            if os.environ.get("WEEKLY_FETCH_FULLTEXT", "0").casefold() in {
                "1",
                "true",
                "yes",
            }:
                content_run = PaperContentWorker().run(connection, issue_id)
            deep_reads = PaperDeepReadAgent(
                backend_from_environment()
            ).run(connection, issue_id)
            renderer = MarkdownRenderAgent()
            renderer.write(connection, issue_id, output_path)
        return WeeklyBuildResult(
            issue_id=issue_id,
            assessed_count=len(assessed),
            trend_count=len(trends),
            selection_count=selection_count,
            estimated_read_minutes=round(minutes, 2),
            output_path=output_path.resolve(),
            version_diffs=version_diffs,
            interpretation_claims=interpretation_claims,
            interpretation_links=interpretation_links,
            deep_reads=deep_reads,
            paper_contents_fetched=(
                content_run.fetched if content_run is not None else 0
            ),
            paper_contents_failed=(
                content_run.failed if content_run is not None else 0
            ),
        )
