from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from .config import (
    department_slug,
    department_source_ids,
    load_departments,
    load_yaml,
)
from .utils import display_title, normalize_title


class SiteDataExportAgent:
    name = "SiteDataExportAgent"

    def _issue_payload(
        self, connection: sqlite3.Connection, issue_id: str
    ) -> dict[str, object]:
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
                   c.title_zh, c.one_sentence_zh, c.problem_zh,
                   c.method_zh, c.result_zh, c.contributions_json,
                   c.evidence_json, c.limitations_json, c.confidence,
                   c.model_version,
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
            LEFT JOIN deep_read_cards c ON c.selection_id=s.selection_id
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
            deep_read = None
            if row["one_sentence_zh"]:
                deep_read = {
                    "titleZh": row["title_zh"],
                    "oneSentenceZh": row["one_sentence_zh"],
                    "problemZh": row["problem_zh"],
                    "methodZh": row["method_zh"],
                    "resultZh": row["result_zh"],
                    "contributions": json.loads(
                        row["contributions_json"] or "[]"
                    ),
                    "evidence": json.loads(row["evidence_json"] or "[]"),
                    "limitations": json.loads(
                        row["limitations_json"] or "[]"
                    ),
                    "confidence": row["confidence"],
                    "modelVersion": row["model_version"],
                }
            sections.setdefault(row["section"], []).append(
                {
                    "position": row["position"],
                    "role": row["content_role"],
                    "itemType": row["item_type"],
                    "title": display_title(row["canonical_title"]),
                    "url": row["canonical_url"],
                    "reason": row["selection_reason"],
                    "summary": row["display_summary"],
                    "implication": row["department_implication"],
                    "readMinutes": row["estimated_read_minutes"],
                    "publishedAt": row["first_published_at"],
                    "updatedAt": row["latest_updated_at"],
                    "status": row["publication_status"] or row["release_status"],
                    "deepRead": deep_read,
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
                "departmentId": issue["department_id"],
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
        return payload

    def export(
        self, connection: sqlite3.Connection, issue_id: str, output: Path
    ) -> Path:
        payload = self._issue_payload(connection, issue_id)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        root = Path(__file__).resolve().parents[2]
        site_app_root = (root / "site" / "app").resolve()
        output_parent = output.resolve().parent
        is_portal_output = (
            output_parent == site_app_root
            or site_app_root in output_parent.parents
        )
        shared_output = site_app_root if is_portal_output else output.parent
        department_id = str(payload["issue"]["departmentId"])
        self.export_library(
            connection,
            root / "config" / "paper_library.yaml",
            shared_output / "library-data.json",
        )
        self.export_sources(connection, shared_output / "source-data.json")
        self.export_archive(
            connection,
            shared_output / "archive-data.json",
            department_id,
        )
        if is_portal_output:
            self.export_departments(
                connection,
                root / "config" / "departments",
                site_app_root / "department-data.json",
            )
        return output.resolve()

    def export_archive(
        self,
        connection: sqlite3.Connection,
        output: Path,
        department_id: str = "orbitinfer",
    ) -> Path:
        issues = connection.execute(
            """
            SELECT issue_id
            FROM weekly_issues
            WHERE department_id=?
            ORDER BY iso_week DESC
            """,
            (department_id,),
        ).fetchall()
        payload = {
            "issues": [
                self._issue_payload(connection, row["issue_id"])
                for row in issues
            ]
        }
        output.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return output.resolve()

    def export_departments(
        self,
        connection: sqlite3.Connection,
        config_directory: Path,
        output: Path,
    ) -> Path:
        root = Path(__file__).resolve().parents[2]
        departments = load_departments(
            config_directory,
            sources_path=root / "config" / "sources.yaml",
        )
        entries: list[dict[str, object]] = []
        for department in departments:
            department_id = str(department["department_id"])
            issue_rows = connection.execute(
                """
                SELECT issue_id
                FROM weekly_issues
                WHERE department_id=?
                ORDER BY iso_week DESC
                """,
                (department_id,),
            ).fetchall()
            reports = [
                self._issue_payload(connection, str(row["issue_id"]))
                for row in issue_rows
            ]
            page = department.get("page", {})
            output_config = department.get("weekly_output", {})
            entries.append(
                {
                    "id": department_id,
                    "slug": department_slug(department),
                    "name": department["name"],
                    "version": department["version"],
                    "enabled": bool(department.get("enabled", True)),
                    "status": department.get(
                        "status",
                        "active" if department.get("enabled", True)
                        else "disabled",
                    ),
                    "mission": department["mission"],
                    "page": page,
                    "owners": department.get("owners", {}),
                    "coreTopics": department.get("core_topics", []),
                    "adjacentTopics": department.get("adjacent_topics", []),
                    "activationRequirements": department.get(
                        "activation_requirements",
                        [],
                    ),
                    "sourceIds": sorted(
                        department_source_ids(department)
                    ),
                    "sectionLabels": output_config.get(
                        "section_labels",
                        {},
                    ),
                    "weeklyOutput": output_config,
                    "currentReport": reports[0] if reports else None,
                    "archive": reports,
                }
            )
        payload = {
            "schemaVersion": 1,
            "departments": entries,
        }
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return output.resolve()

    def export_library(
        self,
        connection: sqlite3.Connection,
        config_path: Path,
        output: Path,
    ) -> Path:
        config = load_yaml(config_path)
        venue_config = load_yaml(config_path.with_name("venues.yaml"))
        papers: list[dict[str, object]] = []
        review_rows = connection.execute(
            """
            SELECT r.canonical_title, r.canonical_url, r.abstract_or_summary,
                   r.first_published_at, d.source_id
            FROM research_items r
            JOIN item_versions v ON v.item_id=r.item_id
            JOIN raw_documents d ON d.raw_document_id=v.raw_document_id
            WHERE r.item_type='review_article'
              AND v.created_at=(
                SELECT MAX(v2.created_at) FROM item_versions v2
                WHERE v2.item_id=r.item_id
              )
            ORDER BY r.first_published_at DESC
            """
        ).fetchall()
        for item in config.get("papers", []):
            title = str(item["title"])
            normalized_title = normalize_title(title)
            tokens = [
                token
                for token in normalized_title.split()
                if len(token) >= 6
                and token not in {"efficient", "inference", "language", "serving"}
            ]
            interpretations = []
            for row in review_rows:
                haystack = normalize_title(
                    " ".join(
                        [
                            row["canonical_title"] or "",
                            row["abstract_or_summary"] or "",
                        ]
                    )
                )
                if normalized_title in haystack or (
                    len(tokens) >= 2
                    and sum(token in haystack for token in tokens) >= 2
                ):
                    interpretations.append(
                        {
                            "title": display_title(row["canonical_title"]),
                            "url": row["canonical_url"],
                            "sourceId": row["source_id"],
                            "publishedAt": row["first_published_at"],
                        }
                    )
            live = connection.execute(
                """
                SELECT r.item_id, r.latest_updated_at,
                       COUNT(v.version_id) AS version_count,
                       MAX(v.change_significance) AS latest_change
                FROM research_items r
                LEFT JOIN item_versions v ON v.item_id=r.item_id
                WHERE r.item_type='paper' AND r.normalized_title=?
                GROUP BY r.item_id
                ORDER BY r.latest_updated_at DESC LIMIT 1
                """,
                (normalized_title,),
            ).fetchone()
            papers.append(
                {
                    "id": item["id"],
                    "title": display_title(title),
                    "titleZh": item["title_zh"],
                    "venue": item["venue"],
                    "year": item["year"],
                    "topic": item["topic"],
                    "status": item["status"],
                    "url": item["url"],
                    "codeUrl": item.get("code_url"),
                    "oneSentenceZh": item["one_sentence_zh"],
                    "whyItMattersZh": item["why_it_matters_zh"],
                    "famousException": bool(item.get("famous_exception", False)),
                    "latestUpdatedAt": live["latest_updated_at"] if live else None,
                    "versionCount": int(live["version_count"]) if live else 0,
                    "latestChange": live["latest_change"] if live else None,
                    "interpretations": interpretations[:3],
                }
            )
        configured_titles = {
            normalize_title(str(paper["title"])) for paper in papers
        }
        live_papers = connection.execute(
            """
            SELECT r.item_id, r.canonical_title, r.canonical_url,
                   r.abstract_or_summary, r.first_published_at,
                   r.latest_updated_at, a.topic_tags_json,
                   (
                       SELECT e.claim_text FROM evidence_claims e
                       WHERE e.item_id=r.item_id
                         AND e.claim_type='publication_status'
                       ORDER BY e.created_at DESC LIMIT 1
                   ) AS publication_status,
                   (
                       SELECT c.title_zh
                       FROM weekly_selections ws
                       JOIN deep_read_cards c
                         ON c.selection_id=ws.selection_id
                       WHERE ws.item_id=r.item_id
                       ORDER BY c.updated_at DESC LIMIT 1
                   ) AS title_zh,
                   (
                       SELECT c.one_sentence_zh
                       FROM weekly_selections ws
                       JOIN deep_read_cards c
                         ON c.selection_id=ws.selection_id
                       WHERE ws.item_id=r.item_id
                       ORDER BY c.updated_at DESC LIMIT 1
                   ) AS one_sentence_zh,
                   (
                       SELECT c.department_implication
                       FROM weekly_selections ws
                       JOIN deep_read_cards c
                         ON c.selection_id=ws.selection_id
                       WHERE ws.item_id=r.item_id
                       ORDER BY c.updated_at DESC LIMIT 1
                   ) AS department_implication,
                   (
                       SELECT COUNT(*) FROM item_versions v
                       WHERE v.item_id=r.item_id
                   ) AS version_count
            FROM research_items r
            JOIN department_assessments a ON a.assessment_id=(
                SELECT a2.assessment_id
                FROM department_assessments a2
                WHERE a2.item_id=r.item_id
                  AND a2.department_id=?
                ORDER BY a2.assessed_at DESC LIMIT 1
            )
            WHERE r.item_type='paper'
              AND r.first_published_at >= datetime('now', '-2 years')
              AND a.department_relevance >= 0.55
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
            """,
            (config["department_id"],),
        ).fetchall()
        for row in live_papers:
            normalized = normalize_title(row["canonical_title"])
            if normalized in configured_titles:
                continue
            topic_tags = json.loads(row["topic_tags_json"] or "[]")
            topic = topic_tags[0] if topic_tags else "inference_runtime"
            papers.append(
                {
                    "id": row["item_id"],
                    "title": display_title(row["canonical_title"]),
                    "titleZh": row["title_zh"] or display_title(
                        row["canonical_title"]
                    ),
                    "venue": row["publication_status"] or "顶会论文",
                    "year": int(str(row["first_published_at"])[:4]),
                    "topic": topic,
                    "status": row["publication_status"] or "顶会论文",
                    "url": row["canonical_url"],
                    "codeUrl": None,
                    "oneSentenceZh": (
                        row["one_sentence_zh"]
                        or "本条目已由自动筛选加入论文库，中文精读摘要待审核补充。"
                    ),
                    "whyItMattersZh": (
                        row["department_implication"]
                        or "近两年新录用且与星载大模型推理引擎方向高度相关。"
                    ),
                    "famousException": False,
                    "latestUpdatedAt": row["latest_updated_at"],
                    "versionCount": int(row["version_count"]),
                    "latestChange": None,
                    "interpretations": [],
                }
            )
            configured_titles.add(normalized)
        payload = {
            "departmentId": config["department_id"],
            "version": config["version"],
            "policy": config["policy"],
            "venues": [
                {
                    "id": venue["id"],
                    "name": venue["name"],
                    "category": venue["category"],
                    "coverage": coverage,
                }
                for coverage, venues in (
                    ("fixed", venue_config.get("fixed_venues", [])),
                    ("supplemental", venue_config.get("supplemental_venues", [])),
                )
                for venue in venues
            ],
            "papers": papers,
        }
        output.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return output.resolve()

    def export_sources(
        self, connection: sqlite3.Connection, output: Path
    ) -> Path:
        rows = connection.execute(
            """
            SELECT s.source_id, s.name, s.tier, s.homepage_url, s.config_json,
                   (
                       SELECT cr.status FROM collection_runs cr
                       WHERE cr.source_id=s.source_id
                       ORDER BY cr.started_at DESC LIMIT 1
                   ) AS run_status,
                   (
                       SELECT cr.stats_json FROM collection_runs cr
                       WHERE cr.source_id=s.source_id
                       ORDER BY cr.started_at DESC LIMIT 1
                   ) AS stats_json,
                   (
                       SELECT cr.finished_at FROM collection_runs cr
                       WHERE cr.source_id=s.source_id
                       ORDER BY cr.started_at DESC LIMIT 1
                   ) AS checked_at
            FROM sources s
            WHERE s.connector='WechatPoolCollector' AND s.enabled=1
            ORDER BY CASE s.tier WHEN 'S_Core' THEN 0 ELSE 1 END, s.name
            """
        ).fetchall()
        accounts = []
        for row in rows:
            options = json.loads(row["config_json"] or "{}")
            stats = json.loads(row["stats_json"] or "{}")
            articles = connection.execute(
                """
                SELECT r.canonical_title, r.canonical_url,
                       r.abstract_or_summary, r.first_published_at
                FROM research_items r
                JOIN item_versions v ON v.item_id=r.item_id
                JOIN raw_documents d ON d.raw_document_id=v.raw_document_id
                WHERE r.item_type='review_article' AND d.source_id=?
                GROUP BY r.item_id
                ORDER BY r.first_published_at DESC LIMIT 6
                """,
                (row["source_id"],),
            ).fetchall()
            health = str(
                stats.get("health_status")
                or ("ok" if row["run_status"] == "ok" else row["run_status"])
                or "not_checked"
            )
            if health == "unchanged":
                health = "no_recent_update"
            if not articles:
                continue
            accounts.append(
                {
                    "sourceId": row["source_id"],
                    "name": row["name"],
                    "tier": row["tier"],
                    "homepageUrl": row["homepage_url"],
                    "accountAlias": options.get("account_alias"),
                    "contentRole": options.get("content_role", "trend_discovery"),
                    "health": health,
                    "runStatus": row["run_status"] or "not_checked",
                    "checkedAt": row["checked_at"],
                    "feedEntries": int(stats.get("feed_entries", 0)),
                    "inWindow": int(stats.get("in_window", 0)),
                    "articles": [
                        {
                            "title": display_title(article["canonical_title"]),
                            "url": article["canonical_url"],
                            "summary": article["abstract_or_summary"],
                            "publishedAt": article["first_published_at"],
                        }
                        for article in articles
                    ],
                }
            )
        output.write_text(
            json.dumps({"accounts": accounts}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return output.resolve()
