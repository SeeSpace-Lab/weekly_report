from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime
from typing import Any

from .models import AssessmentResult
from ..utils import isoformat, json_dumps, normalize_title, utc_now


TOPIC_VOCABULARY: dict[str, tuple[str, ...]] = {
    "inference_runtime": (
        "inference runtime",
        "inference engine",
        "llm serving",
        "continuous batching",
        "prefill",
        "decode",
        "throughput",
        "latency",
        "推理引擎",
        "大模型推理",
    ),
    "scheduling": (
        "scheduling",
        "scheduler",
        "dispatch",
        "placement",
        "load balancing",
        "resource allocation",
        "推理调度",
    ),
    "power_aware": (
        "power",
        "energy",
        "thermal",
        "watt",
        "dvfs",
        "energy efficient",
        "功耗",
        "能耗",
    ),
    "kv_storage": (
        "kv cache",
        "key value cache",
        "cxl",
        "hierarchical memory",
        "offload",
        "memory",
        "缓存",
        "分层存储",
    ),
    "moe_runtime": (
        "mixture of experts",
        "moe",
        "expert placement",
        "expert parallel",
        "expert prefetch",
        "专家放置",
    ),
    "quantization": (
        "quantization",
        "low bit",
        "int4",
        "int8",
        "fp8",
        "compression",
        "量化",
        "压缩",
    ),
    "reliability": (
        "reliability",
        "fault",
        "soft error",
        "recovery",
        "resilien",
        "radiation",
        "容错",
        "可靠推理",
    ),
    "edge_realtime": (
        "edge llm",
        "on device",
        "on-device",
        "mobile",
        "real time",
        "real-time",
        "embedded",
        "端侧",
        "边缘",
    ),
    "distributed_inference": (
        "distributed inference",
        "disaggregated",
        "network aware",
        "migration",
        "multi node",
        "multi-node",
        "分布式推理",
    ),
}

SECTION_BY_TOPIC = {
    "inference_runtime": "inference_and_scheduling",
    "scheduling": "inference_and_scheduling",
    "kv_storage": "kv_storage_moe_quantization",
    "moe_runtime": "kv_storage_moe_quantization",
    "quantization": "kv_storage_moe_quantization",
    "power_aware": "power_reliability_edge_distributed",
    "reliability": "power_reliability_edge_distributed",
    "edge_realtime": "power_reliability_edge_distributed",
    "distributed_inference": "power_reliability_edge_distributed",
}


class DepartmentAssessmentAgent:
    name = "DepartmentAssessmentAgent"
    model_version = "deterministic-assessment-v1"

    def __init__(self, department: dict[str, Any]):
        self.department = department
        self.department_id = str(department["department_id"])
        self.topic_weights = {
            topic["id"]: float(topic.get("weight", 1.0))
            for topic in department.get("core_topics", [])
        }
        self.include_keywords = [
            normalize_title(str(value))
            for value in department.get("keywords", {}).get("include", [])
        ]
        self.exclude_keywords = [
            normalize_title(str(value))
            for value in department.get("keywords", {}).get(
                "exclude_unless_strongly_related", []
            )
        ]

    def assess_row(self, row: sqlite3.Row) -> AssessmentResult:
        text = normalize_title(
            " ".join(
                [
                    row["canonical_title"],
                    row["abstract_or_summary"] or "",
                    row["metadata_text"] or "",
                ]
            )
        )
        topic_scores: dict[str, float] = {}
        for topic_id, vocabulary in TOPIC_VOCABULARY.items():
            matches = sum(
                1 for term in vocabulary if normalize_title(term) in text
            )
            if matches:
                topic_scores[topic_id] = min(
                    1.0,
                    (0.45 + 0.18 * (matches - 1))
                    * self.topic_weights.get(topic_id, 0.7),
                )
        include_hits = sum(1 for term in self.include_keywords if term in text)
        exclusion_hits = sum(1 for term in self.exclude_keywords if term in text)
        strongest = max(topic_scores.values(), default=0.0)
        relevance = min(1.0, strongest + min(0.3, include_hits * 0.06))
        if exclusion_hits and relevance < 0.65:
            relevance *= 0.45

        publication_status = (row["publication_status"] or "").casefold()
        release_status = (row["release_status"] or "").casefold()
        accepted = any(
            marker in publication_status
            for marker in ("accept", "oral", "poster", "spotlight")
        )
        version_count = int(row["version_count"])
        max_version_number = int(row["max_version_number"] or 1)
        identifier_count = int(row["identifier_count"])
        important_revision = max_version_number > 1 and relevance >= 0.55
        artifact_release = bool(release_status) and row["item_type"] in {
            "framework", "benchmark", "dataset"
        }
        authoritative_review = (
            row["item_type"] == "review_article"
            and int(row["interpretation_count"]) > 0
        )
        official_venue_event = row["item_type"] == "venue_event"
        importance = min(
            1.0,
            0.35
            + (0.35 if accepted else 0)
            + (0.18 if important_revision else 0)
            + (0.2 if artifact_release else 0)
            + (0.15 if authoritative_review else 0)
            + (0.2 if official_venue_event else 0)
            + min(0.12, 0.04 * max(0, version_count - 1))
            + min(0.12, 0.04 * max(0, identifier_count - 1)),
        )
        evidence_quality = (
            0.92
            if accepted
            else (
                0.85
                if artifact_release
                else (
                    0.75
                    if authoritative_review
                    else (
                        0.9
                        if official_venue_event
                        else (0.72 if identifier_count > 1 else 0.6)
                    )
                )
            )
        )
        novelty = min(0.9, 0.55 + (0.08 if version_count > 1 else 0))
        trend_signal = min(0.85, 0.4 + 0.08 * len(topic_scores))
        combined = relevance * 0.55 + importance * 0.3 + evidence_quality * 0.15
        if accepted and relevance >= 0.55:
            recommendation = "must_read"
            minutes = 4.0
        elif important_revision and combined >= 0.58:
            recommendation = "recommended"
            minutes = 2.0
        elif artifact_release and relevance >= 0.45:
            recommendation = "recommended"
            minutes = 1.5
        elif authoritative_review and relevance >= 0.4:
            recommendation = "recommended"
            minutes = 1.5
        elif official_venue_event:
            recommendation = "scan"
            minutes = 0.5
        elif exclusion_hits:
            recommendation = "exclude"
            minutes = 0.0
        else:
            recommendation = "archive"
            minutes = 0.0
        tags = tuple(
            topic
            for topic, _ in sorted(
                topic_scores.items(), key=lambda pair: pair[1], reverse=True
            )
        )
        primary_topic = tags[0] if tags else "inference_runtime"
        section = (
            "frameworks_benchmarks_datasets"
            if row["item_type"] in {"framework", "benchmark", "dataset"}
            else (
                "venue_updates"
                if official_venue_event
                else SECTION_BY_TOPIC.get(primary_topic, "inference_and_scheduling")
            )
        )
        reasons = []
        if tags:
            reasons.append("涉及" + "、".join(tags[:3]))
        if accepted:
            reasons.append("具有顶会录用状态")
        if version_count > 1:
            reasons.append(f"检测到{version_count}个版本")
        elif max_version_number > 1:
            reasons.append(f"当前为arXiv v{max_version_number}重要修订候选")
        if not accepted and not important_revision:
            if artifact_release:
                reasons.append("属于官方框架、Benchmark或数据集更新")
            elif authoritative_review:
                reasons.append("来自固定订阅池的权威综述或论文解读")
            elif official_venue_event:
                reasons.append("顶会官方页面发生更新")
            elif row["item_type"] == "paper":
                reasons.append("非顶会新稿且未满足重要版本更新门槛，仅入库不进入周报")
        if not reasons:
            reasons.append("与部门关键词存在弱相关")
        rationale = "；".join(reasons) + "。"
        return AssessmentResult(
            item_id=row["item_id"],
            topic_tags=tags,
            global_importance=round(importance, 3),
            department_relevance=round(relevance, 3),
            novelty=round(novelty, 3),
            evidence_quality=round(evidence_quality, 3),
            trend_signal=round(trend_signal, 3),
            recommendation=recommendation,
            recommended_section=section,
            rationale=rationale,
            estimated_read_minutes=minutes,
        )

    def assess_window(
        self,
        connection: sqlite3.Connection,
        window_start: datetime,
        window_end: datetime,
    ) -> list[tuple[str, AssessmentResult]]:
        rows = connection.execute(
            """
            SELECT r.*,
                   (
                       SELECT claim_text FROM evidence_claims e
                       WHERE e.item_id = r.item_id
                         AND e.claim_type = 'publication_status'
                       ORDER BY e.created_at DESC LIMIT 1
                   ) AS publication_status,
                   (
                       SELECT claim_text FROM evidence_claims er
                       WHERE er.item_id = r.item_id
                         AND er.claim_type = 'release_status'
                       ORDER BY er.created_at DESC LIMIT 1
                   ) AS release_status,
                   (
                       SELECT COUNT(*) FROM evidence_claims ei
                       WHERE ei.item_id=r.item_id
                         AND ei.claim_type='interpretation'
                   ) AS interpretation_count,
                   (
                       SELECT COUNT(*) FROM item_versions v
                       WHERE v.item_id = r.item_id
                   ) AS version_count,
                   (
                       SELECT MAX(COALESCE(version_number, 1))
                       FROM item_versions v0 WHERE v0.item_id = r.item_id
                   ) AS max_version_number,
                   (
                       SELECT COUNT(*) FROM item_identifiers i
                       WHERE i.item_id = r.item_id
                   ) AS identifier_count,
                   (
                       SELECT GROUP_CONCAT(metadata_json, ' ')
                       FROM item_versions v2 WHERE v2.item_id = r.item_id
                   ) AS metadata_text
            FROM research_items r
            WHERE r.latest_updated_at >= ?
              AND r.latest_updated_at <= ?
              AND r.status = 'active'
            ORDER BY r.latest_updated_at DESC
            """,
            (isoformat(window_start), isoformat(window_end)),
        ).fetchall()
        assessed: list[tuple[str, AssessmentResult]] = []
        assessed_at = isoformat(utc_now())
        for row in rows:
            result = self.assess_row(row)
            assessment_id = str(uuid.uuid4())
            connection.execute(
                """
                INSERT INTO department_assessments (
                    assessment_id, department_id, item_id, topic_tags_json,
                    global_importance, department_relevance, novelty,
                    evidence_quality, trend_signal, recommendation,
                    recommended_section, rationale, estimated_read_minutes,
                    model_version, assessed_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    assessment_id,
                    self.department_id,
                    result.item_id,
                    json_dumps(list(result.topic_tags)),
                    result.global_importance,
                    result.department_relevance,
                    result.novelty,
                    result.evidence_quality,
                    result.trend_signal,
                    result.recommendation,
                    result.recommended_section,
                    result.rationale,
                    result.estimated_read_minutes,
                    self.model_version,
                    assessed_at,
                ),
            )
            assessed.append((assessment_id, result))
        return assessed
