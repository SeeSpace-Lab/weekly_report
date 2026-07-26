from __future__ import annotations

import json
import os
import urllib.request
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


class OpenAICompatibleJSONBackend:
    def __init__(self, base_url: str, api_key: str, model: str):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.model_version = f"openai-compatible:{model}"

    def deep_read(self, item: dict[str, Any]) -> DeepReadResult:
        endpoint = (
            f"{self.base_url}/chat/completions"
            if self.base_url.endswith("/v1")
            else f"{self.base_url}/v1/chat/completions"
        )
        schema_instruction = """
仅输出JSON对象，字段必须为：
summary_zh: string；
title_zh: string（准确、简洁的中文标题）；
problem_zh: string（论文解决什么问题）；
method_zh: string（核心方法或系统机制）；
result_zh: string（关键实验结果；无可靠数字时明确说明）；
contributions: string[]；
evidence: string[]；
limitations: string[]；
department_implication: string；
confidence: 0到1数字。
不得把摘要中不存在的信息写成事实；信息不足时明确说明。
"""
        user_payload = {
            "department": "星载大模型推理引擎",
            "task": "为研究员生成周报精读卡片",
            "item": item,
        }
        body = {
            "model": self.model,
            "temperature": 0.1,
            "response_format": {"type": "json_object"},
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "你是严谨的系统与大模型推理研究情报分析员。"
                        + schema_instruction
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps(user_payload, ensure_ascii=False),
                },
            ],
        }
        request = urllib.request.Request(
            endpoint,
            data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=90) as response:
            payload = json.loads(response.read().decode("utf-8"))
        content = payload["choices"][0]["message"]["content"]
        result = json.loads(content)
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


def backend_from_environment() -> AnalysisBackend:
    api_key = os.environ.get("WEEKLY_LLM_API_KEY")
    model = os.environ.get("WEEKLY_LLM_MODEL")
    base_url = os.environ.get(
        "WEEKLY_LLM_BASE_URL", "https://api.openai.com/v1"
    )
    if api_key and model:
        return OpenAICompatibleJSONBackend(base_url, api_key, model)
    return DeterministicAnalysisBackend()
