from __future__ import annotations

import json
import sqlite3
from pathlib import Path


class SiteDataExportAgent:
    name = "SiteDataExportAgent"

    def export(
        self, connection: sqlite3.Connection, issue_id: str, output: Path
    ) -> Path:
        issue = connection.execute(
            "SELECT * FROM weekly_issues WHERE issue_id=?", (issue_id,)
        ).fetchone()
        if not issue:
            raise ValueError(f"issue not found: {issue_id}")
        rows = connection.execute(
            """
            SELECT s.selection_id, s.section, s.position, s.content_role,
                   s.selection_reason, s.display_summary,
                   s.department_implication, s.estimated_read_minutes,
                   r.item_type, r.canonical_title, r.canonical_url,
                   r.first_published_at, r.latest_updated_at,
                   (
                       SELECT claim_text FROM evidence_claims e
                       WHERE e.item_id=r.item_id
                         AND e.claim_type='publication_status'
                       ORDER BY e.created_at DESC LIMIT 1
                   ) AS publication_status,
                   (
                       SELECT claim_text FROM evidence_claims er
                       WHERE er.item_id=r.item_id
                         AND er.claim_type='release_status'
                       ORDER BY er.created_at DESC LIMIT 1
                   ) AS release_status,
                   (
                       SELECT r2.decision FROM editorial_reviews r2
                       WHERE r2.selection_id=s.selection_id
                       ORDER BY r2.created_at DESC LIMIT 1
                   ) AS review_decision
            FROM weekly_selections s
            JOIN research_items r ON r.item_id=s.item_id
            WHERE s.issue_id=?
            ORDER BY s.section, s.position
            """,
            (issue_id,),
        ).fetchall()
        visible = [
            row
            for row in rows
            if row["review_decision"] not in {"reject", "defer"}
        ]
        sections: dict[str, list[dict[str, object]]] = {}
        for row in visible:
            sections.setdefault(row["section"], []).append(
                {
                    "position": row["position"],
                    "role": row["content_role"],
                    "itemType": row["item_type"],
                    "title": row["canonical_title"],
                    "url": row["canonical_url"],
                    "reason": row["selection_reason"],
                    "summary": row["display_summary"],
                    "implication": row["department_implication"],
                    "readMinutes": row["estimated_read_minutes"],
                    "publishedAt": row["first_published_at"],
                    "updatedAt": row["latest_updated_at"],
                    "status": row["publication_status"] or row["release_status"],
                }
            )
        trends = [
            line[2:].strip()
            for line in (issue["summary"] or "").splitlines()
            if line.startswith("- ")
        ]
        payload = {
            "issue": {
                "id": issue["issue_id"],
                "title": issue["title"],
                "isoWeek": issue["iso_week"],
                "windowStart": issue["window_start"],
                "windowEnd": issue["window_end"],
                "status": issue["status"],
                "targetReadMinutes": issue["target_read_minutes"],
                "estimatedReadMinutes": round(
                    sum(
                        float(row["estimated_read_minutes"] or 0)
                        for row in visible
                    ),
                    1,
                ),
                "itemCount": len(visible),
            },
            "trends": trends,
            "sections": [
                {"id": section, "items": items}
                for section, items in sections.items()
            ],
        }
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return output.resolve()
