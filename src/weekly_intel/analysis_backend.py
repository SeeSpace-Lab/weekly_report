from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, replace
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
    model_version = "deterministic-deep-read-v2"

    def deep_read(self, item: dict[str, Any]) -> DeepReadResult:
        abstract = str(item.get("content") or item.get("summary") or "暂无摘要")
        abstract = " ".join(abstract.split())
        title = str(item["title"])
        searchable = f"{title} {abstract}".casefold()
        topics = []
        for keywords, label in (
            (("power", "energy", "thermal"), "动态功耗与热约束"),
            (("schedul", "orchestrat"), "推理调度"),
            (("kv cache", "kv-cache", "cache"), "KV Cache 管理"),
            (("mixture of experts", "moe", "expert"), "MoE 专家调度"),
            (("quant", "low-bit"), "低比特量化"),
            (("edge", "on-device", "embedded"), "端侧推理"),
            (("fault", "reliab", "resilien"), "可靠性与容错"),
            (("distributed", "disaggregat", "cxl"), "分布式推理"),
        ):
            if any(keyword in searchable for keyword in keywords):
                topics.append(label)
        topic_text = "、".join(topics[:3]) or "受限资源下的大模型推理"
        status = item.get("publication_status")
        contribution = (
            f"工作围绕“{title}”研究{topic_text}，具体贡献需结合原文核验。"
        )
        evidence = (
            f"来源记录：{status}" if status else "当前证据来自论文摘要或官方项目说明。"
        )
        return DeepReadResult(
            title_zh=f"{topic_text}相关研究",
            summary_zh=(
                f"一句话读懂：这项工作聚焦{topic_text}，"
                "尝试改善大模型推理的效率、资源适应性或可靠性。"
            ),
            problem_zh=f"研究问题：如何改进{topic_text}，并满足推理系统约束。",
            method_zh=(
                "方法概览：当前为规则生成卡片；具体机制需由模型精读"
                "论文摘要或全文后补全。"
            ),
            result_zh=(
                "关键结果：当前来源未形成可核验的中文定量结论，"
                "发布前需对照原文确认。"
            ),
            contributions=(contribution,),
            evidence=(evidence,),
            limitations=("尚未完成全文级人工复核，实验边界需阅读原文确认。",),
            department_implication=str(
                item.get("assessment_rationale")
                or "可作为星载受限资源推理设计的邻近参考。"
            ),
            confidence=0.55,
            model_version=self.model_version,
        )


class OpenAIResponsesJSONBackend:
    """Evidence-constrained deep reads through the OpenAI Responses API."""

    _schema = {
        "type": "object",
        "properties": {
            "summary_zh": {"type": "string"},
            "title_zh": {"type": "string"},
            "problem_zh": {"type": "string"},
            "method_zh": {"type": "string"},
            "result_zh": {"type": "string"},
            "contributions": {
                "type": "array",
                "items": {"type": "string"},
            },
            "evidence": {
                "type": "array",
                "items": {"type": "string"},
            },
            "limitations": {
                "type": "array",
                "items": {"type": "string"},
            },
            "department_implication": {"type": "string"},
            "confidence": {"type": "number", "minimum": 0, "maximum": 1},
        },
        "required": [
            "summary_zh",
            "title_zh",
            "problem_zh",
            "method_zh",
            "result_zh",
            "contributions",
            "evidence",
            "limitations",
            "department_implication",
            "confidence",
        ],
        "additionalProperties": False,
    }

    def __init__(
        self,
        base_url: str,
        api_key: str,
        model: str,
        max_attempts: int = 3,
    ):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.max_attempts = max_attempts
        self.model_version = f"openai-responses:{model}"

    def deep_read(self, item: dict[str, Any]) -> DeepReadResult:
        endpoint = (
            f"{self.base_url}/responses"
            if self.base_url.endswith("/v1")
            else f"{self.base_url}/v1/responses"
        )
        user_payload = {
            "department": "星载大模型推理引擎",
            "task": "生成可直接进入研究员周报的中文精读卡片",
            "item": item,
        }
        body = {
            "model": self.model,
            "store": False,
            "reasoning": {"effort": "medium"},
            "max_output_tokens": 2500,
            "text": {
                "verbosity": "medium",
                "format": {
                    "type": "json_schema",
                    "name": "weekly_paper_deep_read",
                    "strict": True,
                    "schema": self._schema,
                },
            },
            "input": [
                {
                    "role": "system",
                    "content": (
                        "你是严谨的大模型推理系统研究情报分析员。"
                        "目标是让研究员在一分钟内理解这项工作的研究问题、"
                        "核心机制、实验结果及其对星载受限资源推理的意义。"
                        "只能使用输入中的摘要、正文和来源元数据；不得用记忆补充事实。"
                        "方法要说明机制而非重复标题。结果优先给出原文明确报告的"
                        "数据、基线和实验条件；证据不足时必须写“输入材料未披露”。"
                        "evidence 中逐条写明支持方法或结果的输入原文片段或忠实转述，"
                        "并以“摘要证据：”或“全文证据：”开头。"
                        "不得把推断写成论文结论。department_implication 必须区分"
                        "直接可用价值与邻近参考价值。"
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps(user_payload, ensure_ascii=False),
                },
            ],
        }
        payload = self._request_with_retry(endpoint, body)
        result = json.loads(self._output_text(payload))
        if not result["evidence"]:
            raise ValueError("model returned no evidence")
        return DeepReadResult(
            title_zh=str(result["title_zh"]),
            summary_zh=str(result["summary_zh"]),
            problem_zh=str(result["problem_zh"]),
            method_zh=str(result["method_zh"]),
            result_zh=str(result["result_zh"]),
            contributions=tuple(str(value) for value in result["contributions"]),
            evidence=tuple(str(value) for value in result["evidence"]),
            limitations=tuple(str(value) for value in result["limitations"]),
            department_implication=str(result["department_implication"]),
            confidence=float(result["confidence"]),
            model_version=self.model_version,
        )

    def _request_with_retry(
        self, endpoint: str, body: dict[str, Any]
    ) -> dict[str, Any]:
        last_error: Exception | None = None
        for attempt in range(self.max_attempts):
            request = urllib.request.Request(
                endpoint,
                data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                method="POST",
            )
            try:
                with urllib.request.urlopen(request, timeout=180) as response:
                    return json.loads(response.read().decode("utf-8"))
            except urllib.error.HTTPError as error:
                detail = error.read().decode("utf-8", errors="replace")[:1000]
                last_error = RuntimeError(
                    f"OpenAI API HTTP {error.code}: {detail}"
                )
                if error.code not in {408, 409, 429, 500, 502, 503, 504}:
                    break
            except (OSError, TimeoutError, json.JSONDecodeError) as error:
                last_error = error
            if attempt + 1 < self.max_attempts:
                time.sleep(2**attempt)
        raise RuntimeError("OpenAI deep read failed") from last_error

    @staticmethod
    def _output_text(payload: dict[str, Any]) -> str:
        if payload.get("status") not in {None, "completed"}:
            raise RuntimeError(
                f"OpenAI response incomplete: {payload.get('status')}"
            )
        for output in payload.get("output", []):
            if output.get("type") != "message":
                continue
            for content in output.get("content", []):
                if content.get("type") == "refusal":
                    raise RuntimeError(
                        f"OpenAI refused deep read: {content.get('refusal')}"
                    )
                if content.get("type") == "output_text":
                    return str(content["text"])
        if payload.get("output_text"):
            return str(payload["output_text"])
        raise RuntimeError("OpenAI response did not contain output text")


class FallbackAnalysisBackend:
    """Keep the private draft available while making fallback visible."""

    def __init__(
        self, primary: AnalysisBackend, fallback: AnalysisBackend | None = None
    ):
        self.primary = primary
        self.fallback = fallback or DeterministicAnalysisBackend()
        self.model_version = primary.model_version

    def deep_read(self, item: dict[str, Any]) -> DeepReadResult:
        try:
            return self.primary.deep_read(item)
        except Exception as error:
            fallback_result = self.fallback.deep_read(item)
            return replace(
                fallback_result,
                limitations=(
                    *fallback_result.limitations,
                    f"模型精读失败：{type(error).__name__}；本卡片不可批准发布。",
                ),
                confidence=min(fallback_result.confidence, 0.4),
                model_version=(
                    f"fallback:{self.primary.model_version}:"
                    f"{type(error).__name__}"
                ),
            )


def backend_from_environment() -> AnalysisBackend:
    api_key = os.environ.get("WEEKLY_LLM_API_KEY")
    model = os.environ.get("WEEKLY_LLM_MODEL", "gpt-5.6")
    base_url = os.environ.get(
        "WEEKLY_LLM_BASE_URL", "https://api.openai.com/v1"
    )
    if api_key:
        return FallbackAnalysisBackend(
            OpenAIResponsesJSONBackend(base_url, api_key, model)
        )
    return DeterministicAnalysisBackend()
