from __future__ import annotations

import json
import os
import urllib.request
from dataclasses import dataclass
from typing import Any, Protocol


@dataclass(frozen=True, slots=True)
class DeepReadResult:
    summary_zh: str
    contributions: tuple[str, ...]
    evidence: tuple[str, ...]
    limitations: tuple[str, ...]
    department_implication: str
    confidence: float
    model_version: str

    def __post_init__(self) -> None:
        if not self.summary_zh.strip():
            raise ValueError("summary_zh cannot be empty")
        if not 0 <= self.confidence <= 1:
            raise ValueError("confidence must be between 0 and 1")


class AnalysisBackend(Protocol):
    model_version: str

    def deep_read(self, item: dict[str, Any]) -> DeepReadResult:
        ...


class DeterministicAnalysisBackend:
    model_version = "deterministic-deep-read-v1"

    def deep_read(self, item: dict[str, Any]) -> DeepReadResult:
        abstract = str(item.get("content") or item.get("summary") or "暂无摘要")
        abstract = " ".join(abstract.split())
        status = item.get("publication_status")
        contribution = (
            f"工作围绕“{item['title']}”提出了与部门方向相关的方法或系统。"
        )
        evidence = (
            f"来源记录：{status}" if status else "当前证据来自论文摘要或官方项目说明。"
        )
        return DeepReadResult(
            summary_zh=f"自动摘要：{abstract[:500]}",
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
            summary_zh=str(result["summary_zh"]),
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
