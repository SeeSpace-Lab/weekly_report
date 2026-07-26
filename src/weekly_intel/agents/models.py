from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class AssessmentResult:
    item_id: str
    topic_tags: tuple[str, ...]
    global_importance: float
    department_relevance: float
    novelty: float
    evidence_quality: float
    trend_signal: float
    recommendation: str
    recommended_section: str
    rationale: str
    estimated_read_minutes: float

    def __post_init__(self) -> None:
        for name in (
            "global_importance",
            "department_relevance",
            "novelty",
            "evidence_quality",
            "trend_signal",
        ):
            value = getattr(self, name)
            if not 0 <= value <= 1:
                raise ValueError(f"{name} must be between 0 and 1")
        if self.recommendation not in {
            "must_read",
            "recommended",
            "scan",
            "archive",
            "exclude",
        }:
            raise ValueError("invalid recommendation")
        if self.estimated_read_minutes < 0:
            raise ValueError("estimated_read_minutes cannot be negative")


@dataclass(frozen=True, slots=True)
class TrendCluster:
    topic_id: str
    label: str
    item_ids: tuple[str, ...]
    signal_strength: float
    summary: str
