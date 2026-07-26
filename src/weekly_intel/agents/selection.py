from __future__ import annotations

import json
import sqlite3
import uuid
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any, Iterable

from .models import AssessmentResult, TrendCluster
from ..utils import isoformat, utc_now


class WeeklySelectionAgent:
    name = "WeeklySelectionAgent"
    model_version = "deterministic-selection-v1"

    def __init__(self, department: dict[str, Any]):
        self.department = department
        self.department_id = str(department["department_id"])
        self.output_config = department.get("weekly_output", {})

    @staticmethod
    def _score(result: AssessmentResult) -> float:
        return (
            result.department_relevance * 0.35
            + result.global_importance * 0.3
            + result.novelty * 0.1
            + result.evidence_quality * 0.15
            + result.trend_signal * 0.1
        )

    def build_issue(
        self,
        connection: sqlite3.Connection,
        iso_week: str,
        window_start: datetime,
        window_end: datetime,
        assessments: Iterable[tuple[str, AssessmentResult]],
        trends: list[TrendCluster],
    ) -> tuple[str, int, float]:
        row = connection.execute(
            """
            SELECT issue_id, status FROM weekly_issues
            WHERE department_id = ? AND iso_week = ?
            """,
            (self.department_id, iso_week),
        ).fetchone()
        now = isoformat(utc_now())
        title = f"{self.department['name']}周报 · {iso_week}"
        summary = "\n".join(
            f"- {trend.summary}" for trend in trends[:5]
        ) or "- 本周尚未形成显著趋势簇。"
        if row:
            if row["status"] in {"approved", "published"}:
                raise ValueError(
                    f"cannot rebuild {row['status']} issue {row['issue_id']}"
                )
            issue_id = row["issue_id"]
            connection.execute(
                "DELETE FROM weekly_selections WHERE issue_id = ?",
                (issue_id,),
            )
            connection.execute(
                """
                UPDATE weekly_issues SET window_start=?, window_end=?,
                    status='draft', title=?, summary=?, generated_at=?
                WHERE issue_id=?
                """,
                (
                    isoformat(window_start),
                    isoformat(window_end),
                    title,
                    summary,
                    now,
                    issue_id,
                ),
            )
        else:
            issue_id = str(uuid.uuid4())
            connection.execute(
                """
                INSERT INTO weekly_issues (
                    issue_id, department_id, iso_week, window_start, window_end,
                    status, title, summary, target_read_minutes, generated_at
                ) VALUES (?, ?, ?, ?, ?, 'draft', ?, ?, ?, ?)
                """,
                (
                    issue_id,
                    self.department_id,
                    iso_week,
                    isoformat(window_start),
                    isoformat(window_end),
                    title,
                    summary,
                    int(self.output_config.get("target_read_minutes", 30)),
                    now,
                ),
            )

        target_minutes = float(self.output_config.get("target_read_minutes", 30))
        ranked = sorted(
            (
                (assessment_id, result, self._score(result))
                for assessment_id, result in assessments
                if result.recommendation not in {"archive", "exclude"}
            ),
            key=lambda value: (
                {"must_read": 3, "recommended": 2, "scan": 1}.get(
                    value[1].recommendation, 0
                ),
                value[2],
            ),
            reverse=True,
        )
        selected: list[tuple[str, AssessmentResult, float]] = []
        used_minutes = 0.0
        must_read_max = int(self.output_config.get("must_read_max", 5))
        must_count = 0
        for assessment_id, result, score in ranked:
            if result.recommendation == "must_read":
                if must_count >= must_read_max:
                    continue
                must_count += 1
            if used_minutes + result.estimated_read_minutes > target_minutes:
                continue
            selected.append((assessment_id, result, score))
            used_minutes += result.estimated_read_minutes

        selected_ids = {result.item_id for _, result, _ in selected}
        library_max = int(self.output_config.get("library_review_max", 2))
        library_rows = connection.execute(
            """
            SELECT r.item_id
            FROM research_items r
            WHERE r.item_type='paper'
              AND r.first_published_at < ?
              AND r.first_published_at >= ?
              AND EXISTS (
                  SELECT 1 FROM evidence_claims e
                  WHERE e.item_id=r.item_id
                    AND e.claim_type='publication_status'
                    AND (
                        lower(e.claim_text) LIKE '%accept%'
                        OR lower(e.claim_text) LIKE '%oral%'
                        OR lower(e.claim_text) LIKE '%poster%'
                        OR lower(e.claim_text) LIKE '%spotlight%'
                    )
              )
            ORDER BY r.latest_updated_at DESC
            LIMIT ?
            """,
            (
                isoformat(window_start),
                isoformat(window_end - timedelta(days=730)),
                library_max + len(selected_ids),
            ),
        ).fetchall()

        positions: dict[str, int] = defaultdict(int)
        for assessment_id, result, score in selected:
            section = (
                "must_read"
                if result.recommendation == "must_read"
                else result.recommended_section
            )
            positions[section] += 1
            role = {
                "must_read": "must_read",
                "recommended": "deep_read",
                "scan": "quick_scan",
            }.get(result.recommendation, "quick_scan")
            connection.execute(
                """
                INSERT INTO weekly_selections (
                    selection_id, issue_id, item_id, assessment_id, section,
                    position, content_role, selection_reason, display_summary,
                    department_implication, estimated_read_minutes, created_at
                )
                SELECT ?, ?, r.item_id, ?, ?, ?, ?, ?, r.abstract_or_summary,
                       ?, ?, ?
                FROM research_items r WHERE r.item_id=?
                """,
                (
                    str(uuid.uuid4()),
                    issue_id,
                    assessment_id,
                    section,
                    positions[section],
                    role,
                    f"综合评分 {score:.2f}；{result.rationale}",
                    result.rationale,
                    result.estimated_read_minutes,
                    now,
                    result.item_id,
                ),
            )

        library_added = 0
        for row in library_rows:
            if row["item_id"] in selected_ids or library_added >= library_max:
                continue
            section = "library_review"
            positions[section] += 1
            connection.execute(
                """
                INSERT INTO weekly_selections (
                    selection_id, issue_id, item_id, section, position,
                    content_role, selection_reason, display_summary,
                    department_implication, estimated_read_minutes, created_at
                )
                SELECT ?, ?, item_id, ?, ?, 'library_review',
                       '近两年顶会论文库回看', abstract_or_summary,
                       '作为稳定知识库条目供研究员回溯。', 1.0, ?
                FROM research_items WHERE item_id=?
                """,
                (
                    str(uuid.uuid4()),
                    issue_id,
                    section,
                    positions[section],
                    now,
                    row["item_id"],
                ),
            )
            used_minutes += 1.0
            library_added += 1
        return issue_id, len(selected) + library_added, used_minutes
