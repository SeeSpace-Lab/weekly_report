from __future__ import annotations

import json
import unittest
from unittest.mock import patch

from weekly_intel.analysis_backend import (
    FallbackAnalysisBackend,
    OpenAIResponsesJSONBackend,
)


class _Response:
    def __init__(self, payload: dict[str, object]):
        self.payload = payload

    def __enter__(self) -> "_Response":
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def read(self) -> bytes:
        return json.dumps(self.payload, ensure_ascii=False).encode("utf-8")


class OpenAIResponsesBackendTest(unittest.TestCase):
    def test_parses_evidence_constrained_structured_output(self) -> None:
        result_payload = {
            "summary_zh": "一句话读懂：按功率预算动态切换调度策略。",
            "title_zh": "面向动态功率预算的推理调度",
            "problem_zh": "解决功率波动下的时延和吞吐稳定性问题。",
            "method_zh": "通过在线预算感知器选择批大小和并行策略。",
            "result_zh": "输入材料报告其在给定平台上降低尾时延。",
            "contributions": ["提出预算感知调度器"],
            "evidence": ["全文证据：调度器按实时功率上限选择配置。"],
            "limitations": ["输入节选未披露所有硬件配置。"],
            "department_implication": "可直接参考其在线功率感知接口。",
            "confidence": 0.82,
        }
        api_payload = {
            "status": "completed",
            "output": [
                {
                    "type": "message",
                    "content": [
                        {
                            "type": "output_text",
                            "text": json.dumps(
                                result_payload, ensure_ascii=False
                            ),
                        }
                    ],
                }
            ],
        }
        backend = OpenAIResponsesJSONBackend(
            "https://api.openai.com/v1", "test-key", "gpt-test"
        )
        with patch(
            "weekly_intel.analysis_backend.urllib.request.urlopen",
            return_value=_Response(api_payload),
        ) as urlopen:
            result = backend.deep_read(
                {
                    "title": "Power-aware scheduling",
                    "summary": "abstract",
                    "content": "paper text",
                }
            )
        request = urlopen.call_args.args[0]
        body = json.loads(request.data.decode("utf-8"))
        self.assertTrue(body["text"]["format"]["strict"])
        self.assertFalse(body["store"])
        self.assertEqual(result.confidence, 0.82)
        self.assertEqual(result.method_zh, result_payload["method_zh"])
        self.assertEqual(result.evidence, tuple(result_payload["evidence"]))

    def test_marks_fallback_as_unpublishable(self) -> None:
        class BrokenBackend:
            model_version = "openai-responses:test"

            def deep_read(self, item: dict[str, object]):
                raise RuntimeError("temporary error")

        result = FallbackAnalysisBackend(BrokenBackend()).deep_read(
            {"title": "A paper", "summary": "KV cache"}
        )
        self.assertTrue(result.model_version.startswith("fallback:"))
        self.assertLess(result.confidence, 0.6)
        self.assertIn("不可批准发布", result.limitations[-1])


if __name__ == "__main__":
    unittest.main()
