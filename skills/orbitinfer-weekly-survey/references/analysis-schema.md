# Codex analysis payload

Write UTF-8 JSON to `runs/codex/current-analysis.json`.

```json
{
  "schemaVersion": 1,
  "issueId": "copy from current-brief.json",
  "selections": [
    {
      "itemId": "copy from a candidate",
      "section": "inference_and_scheduling",
      "role": "must_read",
      "readMinutes": 6,
      "selectionReason": "为什么本周值得研究员投入时间",
      "titleZh": "准确、克制的中文标题",
      "oneSentenceZh": "一句话说明做了什么以及为何重要",
      "problemZh": "明确的研究问题和约束",
      "methodZh": "具体机制、系统设计或实验方法",
      "resultZh": "有来源支撑的结果、指标或定性结论",
      "contributions": ["主要贡献"],
      "evidence": ["来源、章节或摘要中支持上述结论的具体信息"],
      "limitations": ["证据边界、未验证内容或适用范围"],
      "departmentImplication": "对星载大模型推理引擎的具体意义",
      "confidence": 0.78
    }
  ]
}
```

Allowed `section` values:

- `must_read`
- `inference_and_scheduling`
- `kv_storage_moe_quantization`
- `power_reliability_edge_distributed`
- `frameworks_benchmarks_datasets`
- `department_relevance`

Allowed `role` values: `must_read`, `deep_read`.

Constraints enforced by the importer:

- 1–8 selections;
- 1–12 minutes per item and no more than 30 minutes total;
- every selection must come from the current issue’s assessed candidate pool;
- method, result, contribution, evidence, implication, and confidence are
  required;
- confidence must be at least `0.60`;
- imported cards are marked `codex-scheduled-task-v1`.
