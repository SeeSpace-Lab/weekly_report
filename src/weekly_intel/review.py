from __future__ import annotations

import sqlite3
import uuid
from pathlib import Path

from .db import Database
from .render import MarkdownRenderAgent
from .utils import isoformat, utc_now


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
