from __future__ import annotations

import sqlite3
import uuid
from collections import defaultdict
from datetime import datetime
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
                    status='draft', title=?, summary=?,
                    target_read_minutes=?, generated_at=?
                WHERE issue_id=?
                """,
                (
                    isoformat(window_start),
                    isoformat(window_end),
                    title,
                    summary,
                    int(self.output_config.get("target_read_minutes", 30)),
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
        item_types = {
            row["item_id"]: row["item_type"]
            for row in connection.execute(
                """
                SELECT item_id, item_type FROM research_items
                WHERE item_id IN (
                    SELECT item_id FROM department_assessments
                    WHERE department_id=? AND assessed_at>=?
                )
                """,
                (self.department_id, isoformat(window_start)),
            ).fetchall()
        }
        selected: list[tuple[str, AssessmentResult, float]] = []
        selected_item_ids: set[str] = set()
        used_minutes = 0.0
        max_items = int(self.output_config.get("max_items", 8))
        max_wechat_items = int(
            self.output_config.get("max_wechat_items", 3)
        )
        must_read_max = int(self.output_config.get("must_read_max", 5))
        must_count = 0

        def add_candidate(
            candidate: tuple[str, AssessmentResult, float]
        ) -> bool:
            nonlocal used_minutes, must_count
            assessment_id, result, score = candidate
            if len(selected) >= max_items:
                return False
            if result.item_id in selected_item_ids:
                return False
            if result.recommendation == "must_read":
                if must_count >= must_read_max:
                    return False
                must_count += 1
            if used_minutes + result.estimated_read_minutes > target_minutes:
                return False
            selected.append(candidate)
            selected_item_ids.add(result.item_id)
            used_minutes += result.estimated_read_minutes
            return True

        # Reserve a small part of the reading budget for high-relevance
        # articles from the fixed WeChat pool. Without this, papers tend to
        # monopolize the top of a purely numerical ranking.
        review_candidates = [
            candidate
            for candidate in ranked
            if item_types.get(candidate[1].item_id) == "review_article"
        ]
        for candidate in review_candidates[:max_wechat_items]:
            add_candidate(candidate)

        for candidate in ranked:
            if len(selected) >= max_items:
                break
            add_candidate(candidate)

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

        return issue_id, len(selected), used_minutes
