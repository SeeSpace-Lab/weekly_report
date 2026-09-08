from __future__ import annotations

import json
import sqlite3
import uuid
from pathlib import Path
from typing import Any

from .config import load_yaml
from .render import MarkdownRenderAgent
from .site_export import SiteDataExportAgent
from .utils import isoformat, utc_now


SCHEMA_VERSION = 1
CODEX_MODEL_VERSION = "codex-scheduled-task-v1"


def reserve_wechat_candidates(
    candidates: list[dict[str, Any]],
    limit: int,
    reserve: int,
) -> list[dict[str, Any]]:
    reserve = min(limit, max(0, reserve))
    wechat_candidates = [
        item for item in candidates if item["isWechat"]
    ]
    other_candidates = [
        item for item in candidates if not item["isWechat"]
    ]
    selected = (
        wechat_candidates[:reserve]
        + other_candidates[
            : max(0, limit - min(reserve, len(wechat_candidates)))
        ]
    )
    selected_ids = {item["itemId"] for item in selected}
    for item in candidates:
        if len(selected) >= limit:
            break
        if item["itemId"] not in selected_ids:
            selected.append(item)
            selected_ids.add(item["itemId"])
    selected.sort(
        key=lambda item: (
            item["ruleAssessment"]["score"],
            item["updatedAt"] or "",
        ),
        reverse=True,
    )
    return selected[:limit]


def _json_list(value: object, field: str, *, required: bool = False) -> list[str]:
    if not isinstance(value, list):
        raise ValueError(f"{field} must be an array")
    result = [str(item).strip() for item in value if str(item).strip()]
    if required and not result:
        raise ValueError(f"{field} cannot be empty")
    return result


def _required_text(record: dict[str, Any], field: str, minimum: int = 1) -> str:
    value = str(record.get(field) or "").strip()
    if len(value) < minimum:
        raise ValueError(f"{field} must contain at least {minimum} characters")
    return value


class CodexWeeklyHandoff:
    """Structured boundary between deterministic collection and Codex curation."""

    def __init__(self, department_path: Path):
        self.department_path = department_path
        self.department = load_yaml(department_path)

    def export_brief(
        self,
        connection: sqlite3.Connection,
        issue_id: str,
        output: Path,
        limit: int = 30,
    ) -> Path:
        issue = connection.execute(
            "SELECT * FROM weekly_issues WHERE issue_id=?", (issue_id,)
        ).fetchone()
        if not issue:
            raise ValueError(f"issue not found: {issue_id}")
        rows = connection.execute(
            """
            SELECT a.assessment_id, a.item_id, a.topic_tags_json,
                   a.global_importance, a.department_relevance, a.novelty,
                   a.evidence_quality, a.trend_signal, a.recommendation,
                   a.recommended_section, a.rationale,
                   a.estimated_read_minutes, r.item_type,
                   r.canonical_title, r.abstract_or_summary,
                   r.canonical_url, r.authors_json,
                   r.first_published_at, r.latest_updated_at,
                   EXISTS(
                       SELECT 1
                       FROM item_versions wv
                       JOIN raw_documents wd
                         ON wd.raw_document_id=wv.raw_document_id
                       WHERE wv.item_id=r.item_id
                         AND wd.canonical_url LIKE
                           'https://mp.weixin.qq.com/%'
                   ) AS is_wechat,
                   COALESCE(
                       (
                           SELECT pc.content_text
                           FROM paper_contents pc
                           WHERE pc.item_id=r.item_id
                           ORDER BY pc.fetched_at DESC LIMIT 1
                       ),
                       (
                           SELECT d.content_text
                           FROM item_versions v
                           JOIN raw_documents d
                             ON d.raw_document_id=v.raw_document_id
                           WHERE v.item_id=r.item_id
                           ORDER BY v.created_at DESC LIMIT 1
                       ),
                       r.abstract_or_summary
                   ) AS evidence_text,
                   (
                       SELECT claim_text FROM evidence_claims e
                       WHERE e.item_id=r.item_id
                         AND e.claim_type IN (
                           'publication_status', 'release_status'
                         )
                       ORDER BY e.created_at DESC LIMIT 1
                   ) AS source_status
            FROM department_assessments a
            JOIN research_items r ON r.item_id=a.item_id
            WHERE a.department_id=?
              AND a.assessed_at>=?
              AND r.latest_updated_at>=?
              AND r.latest_updated_at<=?
              AND (
                  r.item_type<>'paper'
                  OR r.first_published_at>=?
                  OR a.recommendation IN ('must_read', 'recommended')
              )
              AND a.assessed_at=(
                  SELECT MAX(a2.assessed_at)
                  FROM department_assessments a2
                  WHERE a2.department_id=a.department_id
                    AND a2.item_id=a.item_id
                    AND a2.assessed_at>=?
              )
            """,
            (
                issue["department_id"],
                issue["window_start"],
                issue["window_start"],
                issue["window_end"],
                issue["window_start"],
                issue["window_start"],
            ),
        ).fetchall()
        candidates = []
        min_relevance = float(
            self.department.get("candidate_policy", {}).get(
                "min_codex_brief_relevance",
                0.0,
            )
        )
        for row in rows:
            if float(row["department_relevance"]) < min_relevance:
                continue
            score = (
                0.25 * float(row["global_importance"])
                + 0.30 * float(row["department_relevance"])
                + 0.15 * float(row["novelty"])
                + 0.15 * float(row["evidence_quality"])
                + 0.15 * float(row["trend_signal"])
            )
            candidates.append(
                {
                    "assessmentId": row["assessment_id"],
                    "itemId": row["item_id"],
                    "itemType": row["item_type"],
                    "title": row["canonical_title"],
                    "url": row["canonical_url"],
                    "authors": json.loads(row["authors_json"] or "[]"),
                    "summary": row["abstract_or_summary"],
                    "evidenceText": str(row["evidence_text"] or "")[:36_000],
                    "sourceStatus": row["source_status"],
                    "publishedAt": row["first_published_at"],
                    "updatedAt": row["latest_updated_at"],
                    "isWechat": bool(row["is_wechat"]),
                    "topicTags": json.loads(row["topic_tags_json"] or "[]"),
                    "ruleAssessment": {
                        "score": round(score, 4),
                        "recommendation": row["recommendation"],
                        "recommendedSection": row["recommended_section"],
                        "rationale": row["rationale"],
                        "estimatedReadMinutes": row[
                            "estimated_read_minutes"
                        ],
                    },
                }
            )
        candidates.sort(
            key=lambda item: (
                item["ruleAssessment"]["score"],
                item["updatedAt"] or "",
            ),
            reverse=True,
        )
        reserve = min(
            limit,
            int(
                self.department.get("weekly_output", {}).get(
                    "wechat_candidate_reserve", 8
                )
            ),
        )
        selected_candidates = reserve_wechat_candidates(
            candidates,
            limit,
            reserve,
        )

        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(
            json.dumps(
                {
                    "schemaVersion": SCHEMA_VERSION,
                    "issueId": issue["issue_id"],
                    "isoWeek": issue["iso_week"],
                    "department": {
                        "id": self.department["department_id"],
                        "name": self.department["name"],
                        "mission": self.department.get("mission"),
                        "coreTopics": self.department.get("core_topics", []),
                        "adjacentTopics": self.department.get(
                            "adjacent_topics",
                            [],
                        ),
                        "keywords": self.department.get("keywords", {}),
                        "paperWatchlist": self.department.get(
                            "paper_watchlist",
                            [],
                        ),
                        "sourcePool": self.department.get("source_pool", {}),
                        "contentRequirements": self.department.get(
                            "content_requirements",
                            {},
                        ),
                        "editorialGuidance": self.department.get(
                            "editorial_guidance",
                            {},
                        ),
                        "triagePolicy": self.department.get(
                            "triage_policy",
                            {},
                        ),
                        "investigationIndex": self.department.get(
                            "investigation_index",
                            {},
                        ),
                        "candidatePolicy": self.department.get(
                            "candidate_policy",
                            {},
                        ),
                    },
                    "constraints": self.department.get("weekly_output", {}),
                    "instructions": [
                        "规则评分只用于形成候选池，最终筛选由 Codex 独立完成。",
                        "只保留本周真正值得研究员花时间阅读的项目。",
                        "强相关与补充内容都必须属于本周七天时间窗；先输出强相关项目，再用 quick_scan 短卡片补充次相关论文、公众号或新闻。总阅读量尽量达到 minimum_read_minutes，但不得超过 target_read_minutes。",
                        "论文优先顶会接收、重要新版本或强相关邻近研究。",
                        "公众号解读只能作为辅助，事实必须回到论文、官网或仓库核验。",
                        "方法、结果和证据不得根据标题臆测；证据不足时降低置信度并写明局限。",
                        "逐项遵守部门 contentRequirements 和 editorialGuidance；具体内容与判断必须分开写。",
                    ],
                    "candidates": selected_candidates[:limit],
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        return output.resolve()

    def import_analysis(
        self,
        connection: sqlite3.Connection,
        payload_path: Path,
        output_path: Path,
        site_data_path: Path,
    ) -> tuple[str, int]:
        payload = json.loads(payload_path.read_text(encoding="utf-8"))
        if payload.get("schemaVersion") != SCHEMA_VERSION:
            raise ValueError("unsupported Codex handoff schema version")
        issue_id = _required_text(payload, "issueId")
        issue = connection.execute(
            "SELECT * FROM weekly_issues WHERE issue_id=?", (issue_id,)
        ).fetchone()
        if not issue:
            raise ValueError(f"issue not found: {issue_id}")
        if issue["status"] in {"approved", "published"}:
            raise ValueError("approved or published issue cannot be replaced")
        selections = payload.get("selections")
        if not isinstance(selections, list):
            raise ValueError("selections must be an array")
        output_config = self.department.get("weekly_output", {})
        max_items = int(output_config.get("max_items", 8))
        min_items = int(output_config.get("min_items", 1))
        if len(selections) < min_items:
            raise ValueError(
                f"selections below min_items={min_items}: "
                f"got {len(selections)}"
            )
        if len(selections) > max_items:
            raise ValueError(f"selections exceeds max_items={max_items}")
        allowed_sections = set(output_config.get("sections", []))
        allowed_sections.discard("weekly_trends")
        target_minutes = float(output_config.get("target_read_minutes", 30))

        assessment_rows = connection.execute(
            """
            SELECT a.assessment_id, a.item_id
            FROM department_assessments a
            JOIN research_items r ON r.item_id=a.item_id
            WHERE a.department_id=? AND a.assessed_at>=?
              AND r.latest_updated_at>=?
              AND r.latest_updated_at<=?
              AND a.assessed_at=(
                  SELECT MAX(a2.assessed_at)
                  FROM department_assessments a2
                  WHERE a2.department_id=a.department_id
                    AND a2.item_id=a.item_id
                    AND a2.assessed_at>=?
              )
            """,
            (
                issue["department_id"],
                issue["window_start"],
                issue["window_start"],
                issue["window_end"],
                issue["window_start"],
            ),
        ).fetchall()
        assessments = {
            str(row["item_id"]): str(row["assessment_id"])
            for row in assessment_rows
        }
        item_ids: set[str] = set()
        normalized: list[dict[str, Any]] = []
        total_minutes = 0.0
        for record in selections:
            if not isinstance(record, dict):
                raise ValueError("each selection must be an object")
            item_id = _required_text(record, "itemId")
            if item_id in item_ids:
                raise ValueError(f"duplicate itemId: {item_id}")
            if item_id not in assessments:
                raise ValueError(f"item was not assessed in this issue: {item_id}")
            item_ids.add(item_id)
            section = _required_text(record, "section")
            if section not in allowed_sections:
                raise ValueError(f"unsupported section: {section}")
            role = _required_text(record, "role")
            if role not in {"must_read", "deep_read", "quick_scan"}:
                raise ValueError(f"unsupported role: {role}")
            read_minutes = float(record.get("readMinutes") or 0)
            if not 1 <= read_minutes <= 12:
                raise ValueError("readMinutes must be between 1 and 12")
            total_minutes += read_minutes
            confidence = float(record.get("confidence") or 0)
            if not 0.6 <= confidence <= 1:
                raise ValueError("confidence must be between 0.6 and 1")
            normalized.append(
                {
                    "item_id": item_id,
                    "assessment_id": assessments[item_id],
                    "section": section,
                    "role": role,
                    "read_minutes": read_minutes,
                    "selection_reason": _required_text(
                        record, "selectionReason", 12
                    ),
                    "title_zh": _required_text(record, "titleZh", 4),
                    "summary_zh": _required_text(
                        record, "oneSentenceZh", 18
                    ),
                    "problem_zh": _required_text(record, "problemZh", 18),
                    "method_zh": _required_text(record, "methodZh", 24),
                    "result_zh": _required_text(record, "resultZh", 18),
                    "contributions": _json_list(
                        record.get("contributions"),
                        "contributions",
                        required=True,
                    ),
                    "evidence": _json_list(
                        record.get("evidence"), "evidence", required=True
                    ),
                    "limitations": _json_list(
                        record.get("limitations"), "limitations"
                    ),
                    "implication": _required_text(
                        record, "departmentImplication", 12
                    ),
                    "confidence": confidence,
                }
            )
        if total_minutes > target_minutes:
            raise ValueError(
                f"total read time {total_minutes:.1f} exceeds "
                f"target {target_minutes:.1f}"
            )

        connection.execute(
            "DELETE FROM weekly_selections WHERE issue_id=?", (issue_id,)
        )
        now = isoformat(utc_now())
        positions: dict[str, int] = {}
        for record in normalized:
            section = record["section"]
            positions[section] = positions.get(section, 0) + 1
            selection_id = str(uuid.uuid4())
            display_summary = (
                f"**中文标题：** {record['title_zh']}\n\n"
                f"**{record['summary_zh']}**\n\n"
                f"{record['problem_zh']}\n\n"
                f"{record['method_zh']}\n\n"
                f"{record['result_zh']}"
            )
            connection.execute(
                """
                INSERT INTO weekly_selections (
                    selection_id, issue_id, item_id, assessment_id, section,
                    position, content_role, selection_reason, display_summary,
                    department_implication, estimated_read_minutes,
                    requires_human_review, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?)
                """,
                (
                    selection_id,
                    issue_id,
                    record["item_id"],
                    record["assessment_id"],
                    section,
                    positions[section],
                    record["role"],
                    record["selection_reason"],
                    display_summary,
                    record["implication"],
                    record["read_minutes"],
                    now,
                ),
            )
            connection.execute(
                """
                INSERT INTO deep_read_cards (
                    selection_id, title_zh, one_sentence_zh, problem_zh,
                    method_zh, result_zh, contributions_json, evidence_json,
                    limitations_json, department_implication, confidence,
                    model_version, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    selection_id,
                    record["title_zh"],
                    record["summary_zh"],
                    record["problem_zh"],
                    record["method_zh"],
                    record["result_zh"],
                    json.dumps(record["contributions"], ensure_ascii=False),
                    json.dumps(record["evidence"], ensure_ascii=False),
                    json.dumps(record["limitations"], ensure_ascii=False),
                    record["implication"],
                    record["confidence"],
                    CODEX_MODEL_VERSION,
                    now,
                    now,
                ),
            )
        connection.execute(
            """
            UPDATE weekly_issues
            SET status='review', generated_at=?
            WHERE issue_id=?
            """,
            (now, issue_id),
        )
        MarkdownRenderAgent().write(connection, issue_id, output_path)
        SiteDataExportAgent().export(connection, issue_id, site_data_path)
        return issue_id, len(normalized)


def default_department_path(root: Path) -> Path:
    return root / "config" / "departments" / "orbitinfer.yaml"
