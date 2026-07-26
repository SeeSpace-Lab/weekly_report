from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


@dataclass(frozen=True, slots=True)
class DeepReadResult:
    title_zh: str
    summary_zh: str
    problem_zh: str
    method_zh: str
    result_zh: str
    contributions: tuple[str, ...]
    evidence: tuple[str, ...]
    limitations: tuple[str, ...]
    department_implication: str
    confidence: float
    model_version: str

    def __post_init__(self) -> None:
        for field_name in (
            "title_zh",
            "summary_zh",
            "problem_zh",
            "method_zh",
            "result_zh",
        ):
            if not getattr(self, field_name).strip():
                raise ValueError(f"{field_name} cannot be empty")
        if not 0 <= self.confidence <= 1:
            raise ValueError("confidence must be between 0 and 1")


class AnalysisBackend(Protocol):
    model_version: str

    def deep_read(self, item: dict[str, Any]) -> DeepReadResult:
        ...


class DeterministicAnalysisBackend:
    """Create an explicitly unpublishable placeholder before Codex curation."""

    model_version = "deterministic-codex-handoff-v1"

    def deep_read(self, item: dict[str, Any]) -> DeepReadResult:
        title = str(item["title"])
        status = str(item.get("publication_status") or "").strip()
        evidence = (
            f"当前来源状态：{status}"
            if status
            else "当前候选只有采集来源或摘要，尚未由 Codex 核验。"
        )
        rationale = str(
            item.get("assessment_rationale")
            or "规则评分认为该项目可能与部门方向相关。"
        )
        return DeepReadResult(
            title_zh=f"{title}（待 Codex 精读）",
            summary_zh="本条目已进入候选池，尚未完成 Codex 原始来源核验。",
            problem_zh="研究问题待 Codex 阅读论文、项目官网或仓库后确认。",
            method_zh="方法待 Codex 根据原始来源提取，不根据标题或关键词推测。",
            result_zh="结果待 Codex 核验；当前卡片不得进入审核通过流程。",
            contributions=("尚未完成 Codex 精读。",),
            evidence=(evidence,),
            limitations=("规则候选卡片，不可批准或公开发布。",),
            department_implication=rationale,
            confidence=0.35,
            model_version=self.model_version,
        )


def backend_from_environment() -> AnalysisBackend:
    """The application never calls an external model API.

    Codex scheduled tasks replace these placeholders through the structured
    export/import handoff.
    """

    return DeterministicAnalysisBackend()
