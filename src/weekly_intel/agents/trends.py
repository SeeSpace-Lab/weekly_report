from __future__ import annotations

import json
from collections import defaultdict
from typing import Any, Iterable

from .models import AssessmentResult, TrendCluster


class TrendClusteringAgent:
    name = "TrendClusteringAgent"
    model_version = "deterministic-trends-v1"

    def __init__(self, department: dict[str, Any]):
        self.labels = {
            topic["id"]: topic.get("label", topic["id"])
            for topic in department.get("core_topics", [])
        }

    def cluster(
        self, assessments: Iterable[AssessmentResult]
    ) -> list[TrendCluster]:
        groups: dict[str, list[AssessmentResult]] = defaultdict(list)
        for assessment in assessments:
            if assessment.recommendation in {"archive", "exclude"}:
                continue
            for topic in assessment.topic_tags[:2] or ("other",):
                groups[topic].append(assessment)
        clusters = []
        for topic, members in groups.items():
            average = sum(member.trend_signal for member in members) / len(members)
            strength = min(1.0, average * 0.65 + min(0.35, len(members) * 0.07))
            clusters.append(
                TrendCluster(
                    topic_id=topic,
                    label=self.labels.get(topic, "其他相关进展"),
                    item_ids=tuple(member.item_id for member in members),
                    signal_strength=round(strength, 3),
                    summary=f"本周有{len(members)}项相关进展，集中在{self.labels.get(topic, topic)}。",
                )
            )
        return sorted(
            clusters,
            key=lambda cluster: (cluster.signal_strength, len(cluster.item_ids)),
            reverse=True,
        )
