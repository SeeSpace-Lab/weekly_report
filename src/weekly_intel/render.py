from __future__ import annotations

import sqlite3
from pathlib import Path


SECTION_TITLES = {
    "must_read": "本周必读",
    "inference_and_scheduling": "推理引擎与调度",
    "kv_storage_moe_quantization": "KV Cache、MoE与量化",
    "power_reliability_edge_distributed": "功耗、可靠性、边缘与分布式",
    "frameworks_benchmarks_datasets": "框架、Benchmark与数据集",
    "venue_updates": "顶会动态",
    "library_review": "近两年顶会论文库回看",
}


class MarkdownRenderAgent:
    name = "MarkdownRenderAgent"

    def render(self, connection: sqlite3.Connection, issue_id: str) -> str:
        issue = connection.execute(
            "SELECT * FROM weekly_issues WHERE issue_id=?", (issue_id,)
        ).fetchone()
        if not issue:
            raise ValueError(f"issue not found: {issue_id}")
        rows = connection.execute(
            """
            SELECT s.*, r.canonical_title, r.canonical_url, r.authors_json,
                   r.first_published_at, r.latest_updated_at,
                   (
                       SELECT claim_text FROM evidence_claims e
                       WHERE e.item_id=r.item_id
                         AND e.claim_type='publication_status'
                       ORDER BY e.created_at DESC LIMIT 1
                   ) AS publication_status
            FROM weekly_selections s
            JOIN research_items r ON r.item_id=s.item_id
            WHERE s.issue_id=?
            ORDER BY
                CASE s.section
                    WHEN 'must_read' THEN 1
                    WHEN 'inference_and_scheduling' THEN 2
                    WHEN 'kv_storage_moe_quantization' THEN 3
                    WHEN 'power_reliability_edge_distributed' THEN 4
                    WHEN 'frameworks_benchmarks_datasets' THEN 5
                    WHEN 'venue_updates' THEN 6
                    WHEN 'library_review' THEN 7
                    ELSE 8
                END,
                s.position
            """,
            (issue_id,),
        ).fetchall()
        latest_decisions = {
            row["selection_id"]: row["decision"]
            for row in connection.execute(
                """
                SELECT r.selection_id, r.decision
                FROM editorial_reviews r
                WHERE r.issue_id=? AND r.created_at=(
                    SELECT MAX(r2.created_at)
                    FROM editorial_reviews r2
                    WHERE r2.selection_id=r.selection_id
                )
                """,
                (issue_id,),
            ).fetchall()
        }
        lines = [
            f"# {issue['title']}",
            "",
            f"> 时间窗口：{issue['window_start']} — {issue['window_end']}",
            f"> 目标阅读时间：约 {issue['target_read_minutes']} 分钟",
            "",
            "## 本周趋势",
            "",
            issue["summary"] or "- 暂无。",
            "",
        ]
        current_section = None
        for row in rows:
            if latest_decisions.get(row["selection_id"]) in {"reject", "defer"}:
                continue
            if row["section"] != current_section:
                current_section = row["section"]
                lines.extend(
                    [
                        f"## {SECTION_TITLES.get(current_section, current_section)}",
                        "",
                    ]
                )
            status = (
                f"；{row['publication_status']}"
                if row["publication_status"]
                else ""
            )
            summary_limits = {
                "must_read": 900,
                "deep_read": 650,
                "quick_scan": 180,
                "library_review": 280,
            }
            summary = row["display_summary"] or "暂无摘要。"
            limit = summary_limits.get(row["content_role"], 240)
            if len(summary) > limit:
                summary = summary[:limit].rstrip() + "……"
            lines.extend(
                [
                    f"### {row['position']}. [{row['canonical_title']}]({row['canonical_url']})",
                    "",
                    f"- 推荐理由：{row['selection_reason']}",
                    f"- 部门意义：{row['department_implication'] or '待补充'}",
                    f"- 时间：{row['first_published_at'] or '未知'}{status}",
                    f"- 建议阅读：{row['estimated_read_minutes'] or 0:g} 分钟",
                    "",
                    summary,
                    "",
                ]
            )
        lines.extend(
            [
                "---",
                "",
                "本周报由自动化情报流水线生成，录用状态与关键判断在发布前仍需人工复核。",
                "",
            ]
        )
        return "\n".join(lines)

    def write(
        self, connection: sqlite3.Connection, issue_id: str, output: Path
    ) -> Path:
        content = self.render(connection, issue_id)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(content, encoding="utf-8")
        connection.execute(
            "UPDATE weekly_issues SET output_markdown_url=? WHERE issue_id=?",
            (str(output.resolve()), issue_id),
        )
        return output
