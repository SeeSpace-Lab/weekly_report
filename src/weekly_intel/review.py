from __future__ import annotations

import sqlite3
import uuid
from dataclasses import dataclass
from pathlib import Path

from .db import Database
from .render import MarkdownRenderAgent
from .site_export import SiteDataExportAgent
from .utils import isoformat, utc_now


@dataclass(frozen=True, slots=True)
class ApprovalReadiness:
    issue_id: str
    iso_week: str
    status: str
    ready: bool
    blockers: tuple[str, ...]


class ReviewService:
    def __init__(self, database: Database):
        self.database = database

    def review_selection(
        self,
        selection_id: str,
        reviewer: str,
        decision: str,
        comment: str | None = None,
    ) -> str:
        if decision not in {"approve", "reject", "revise", "defer"}:
            raise ValueError(f"invalid review decision: {decision}")
        review_id = str(uuid.uuid4())
        with self.database.transaction() as connection:
            selection = connection.execute(
                """
                SELECT s.issue_id, i.status, i.output_markdown_url
                FROM weekly_selections s
                JOIN weekly_issues i ON i.issue_id=s.issue_id
                WHERE s.selection_id=?
                """,
                (selection_id,),
            ).fetchone()
            if not selection:
                raise ValueError(f"selection not found: {selection_id}")
            if selection["status"] in {"approved", "published"}:
                raise ValueError(
                    f"cannot review selection in {selection['status']} issue"
                )
            connection.execute(
                """
                INSERT INTO editorial_reviews (
                    review_id, issue_id, selection_id, reviewer,
                    decision, comment, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    review_id,
                    selection["issue_id"],
                    selection_id,
                    reviewer,
                    decision,
                    comment,
                    isoformat(utc_now()),
                ),
            )
            connection.execute(
                """
                UPDATE weekly_selections SET requires_human_review=?
                WHERE selection_id=?
                """,
                (0 if decision in {"approve", "reject"} else 1, selection_id),
            )
            connection.execute(
                "UPDATE weekly_issues SET status='review' WHERE issue_id=?",
                (selection["issue_id"],),
            )
            if selection["output_markdown_url"]:
                MarkdownRenderAgent().write(
                    connection,
                    selection["issue_id"],
                    Path(selection["output_markdown_url"]),
                )
        return review_id

    def approve_issue(self, issue_id: str) -> None:
        with self.database.transaction() as connection:
            issue = connection.execute(
                "SELECT status FROM weekly_issues WHERE issue_id=?", (issue_id,)
            ).fetchone()
            if not issue:
                raise ValueError(f"issue not found: {issue_id}")
            if issue["status"] == "published":
                raise ValueError("published issue cannot be re-approved")
            pending = connection.execute(
                """
                SELECT COUNT(*)
                FROM weekly_selections s
                WHERE s.issue_id=?
                  AND NOT EXISTS (
                      SELECT 1 FROM editorial_reviews r
                      WHERE r.selection_id=s.selection_id
                        AND r.created_at=(
                            SELECT MAX(r2.created_at)
                            FROM editorial_reviews r2
                            WHERE r2.selection_id=s.selection_id
                        )
                        AND r.decision IN ('approve', 'reject')
                  )
                """,
                (issue_id,),
            ).fetchone()[0]
            if pending:
                raise ValueError(f"{pending} selections still require review")
            connection.execute(
                """
                UPDATE weekly_issues SET status='approved', approved_at=?
                WHERE issue_id=?
                """,
                (isoformat(utc_now()), issue_id),
            )

    def current_issue_id(self, department_id: str = "orbitinfer") -> str:
        with self.database.session() as connection:
            row = connection.execute(
                """
                SELECT issue_id FROM weekly_issues
                WHERE department_id=?
                ORDER BY iso_week DESC, created_at DESC LIMIT 1
                """,
                (department_id,),
            ).fetchone()
        if not row:
            raise ValueError(f"no issue found for department: {department_id}")
        return str(row["issue_id"])

    def approval_readiness(self, issue_id: str) -> ApprovalReadiness:
        with self.database.session() as connection:
            issue = connection.execute(
                """
                SELECT issue_id, iso_week, status
                FROM weekly_issues WHERE issue_id=?
                """,
                (issue_id,),
            ).fetchone()
            if not issue:
                raise ValueError(f"issue not found: {issue_id}")
            rows = connection.execute(
                """
                SELECT s.content_role, r.canonical_title,
                       c.method_zh, c.result_zh, c.evidence_json,
                       c.confidence, c.model_version
                FROM weekly_selections s
                JOIN research_items r ON r.item_id=s.item_id
                LEFT JOIN deep_read_cards c ON c.selection_id=s.selection_id
                WHERE s.issue_id=?
                  AND s.section NOT IN ('venue_updates', 'library_review')
                  AND s.content_role IN ('must_read', 'deep_read')
                ORDER BY s.section, s.position
                """,
                (issue_id,),
            ).fetchall()
        blockers: list[str] = []
        if not rows:
            blockers.append("本期没有可审核的精读条目")
        for row in rows:
            title = str(row["canonical_title"])
            model_version = str(row["model_version"] or "")
            if (
                not row["method_zh"]
                or not row["result_zh"]
                or not row["evidence_json"]
            ):
                blockers.append(f"《{title}》缺少方法、结果或证据")
                continue
            if model_version.startswith(("deterministic", "fallback:")):
                blockers.append(f"《{title}》仍是规则占位卡片")
            if float(row["confidence"] or 0) < 0.6:
                blockers.append(f"《{title}》精读置信度低于 0.60")
        return ApprovalReadiness(
            issue_id=str(issue["issue_id"]),
            iso_week=str(issue["iso_week"]),
            status=str(issue["status"]),
            ready=not blockers,
            blockers=tuple(blockers),
        )

    def approve_all_and_export(
        self,
        issue_id: str,
        reviewer: str,
        output: Path,
    ) -> ApprovalReadiness:
        readiness = self.approval_readiness(issue_id)
        if readiness.status == "published":
            raise ValueError("published issue cannot be re-approved")
        if not readiness.ready:
            raise ValueError("; ".join(readiness.blockers))
        with self.database.session() as connection:
            rows = connection.execute(
                """
                SELECT s.selection_id, s.section,
                       (
                           SELECT r.decision FROM editorial_reviews r
                           WHERE r.selection_id=s.selection_id
                           ORDER BY r.created_at DESC LIMIT 1
                       ) AS latest_decision
                FROM weekly_selections s
                WHERE s.issue_id=?
                ORDER BY s.section, s.position
                """,
                (issue_id,),
            ).fetchall()
        for row in rows:
            if row["latest_decision"] == "reject":
                continue
            decision = (
                "reject"
                if row["section"] in {"venue_updates", "library_review"}
                else "approve"
            )
            if row["latest_decision"] == decision:
                continue
            self.review_selection(
                str(row["selection_id"]),
                reviewer=reviewer,
                decision=decision,
                comment=(
                    "整期审核确认"
                    if decision == "approve"
                    else "不进入部门周报正文"
                ),
            )
        self.approve_issue(issue_id)
        with self.database.transaction() as connection:
            SiteDataExportAgent().export(connection, issue_id, output)
        return self.approval_readiness(issue_id)

    def publish_issue(self, issue_id: str, page_url: str | None = None) -> None:
        with self.database.transaction() as connection:
            issue = connection.execute(
                """
                SELECT status, output_markdown_url
                FROM weekly_issues WHERE issue_id=?
                """,
                (issue_id,),
            ).fetchone()
            if not issue:
                raise ValueError(f"issue not found: {issue_id}")
            if issue["status"] != "approved":
                raise ValueError("only approved issues can be published")
            if not issue["output_markdown_url"] or not Path(
                issue["output_markdown_url"]
            ).exists():
                raise ValueError("rendered output is missing")
            connection.execute(
                """
                UPDATE weekly_issues SET status='published', published_at=?,
                    output_page_url=COALESCE(?, output_page_url)
                WHERE issue_id=?
                """,
                (isoformat(utc_now()), page_url, issue_id),
            )
