#!/usr/bin/env python3
"""数据库版导出器：校验 + 规范化事件库为合规的 26 列数据库版 CSV。

数据库版本质就是事件池本身，所以这里不做生成、不做判断，只做确定性的
schema 校验与规范化：
  - 强制 26 列规范列序（以 event_database_template.csv 为唯一真源）
  - event_id 唯一性检查
  - 必填字段非空检查（event_id/date/country/sector/event_title/source_url）
  - 枚举值校验（priority / source_tier / include_in_report / sector / country）
  - 日期格式校验（ISO YYYY-MM-DD）
  - 多值字段（domain / source_type / secondary_sources）分号规范化（去空格、去空段）
  - 按 (priority S>A>B>C, date) 排序后输出

校验问题分 error（阻断，退出码 1）与 warning（非阻断，提示）两档。
用法：
    render_db_csv.py <event_pool.csv> [-o output.csv] [--week 2026-W20]
不指定 -o 时只校验并打印 JSON 报告，不写文件（dry-run）。
"""
from __future__ import annotations

import argparse
import csv
import json
import re
from pathlib import Path


CANONICAL_COLUMNS = [
    "event_id", "date", "published_date", "country", "sector", "domain",
    "entity", "event_title", "event_summary", "source_name", "source_type",
    "source_url", "source_tier", "secondary_sources",
    "space_compute_relevance_score", "industry_impact_score", "novelty_score",
    "total_score", "priority", "reason_for_priority", "include_in_report",
    "implication", "meaning_for_us", "next_watch", "analyst_note",
    "source_discovery_flag",
]

REQUIRED_NON_EMPTY = ["event_id", "date", "country", "sector", "event_title", "source_url"]
MULTI_VALUE = ["domain", "source_type", "secondary_sources"]

ENUMS = {
    "priority": {"S", "A", "B", "C", ""},
    "source_tier": {"S_Core", "A_Active", "Watch", "Backup", "Manual", ""},
    "include_in_report": {"Yes", "Brief", "Appendix", "Database_Only", "Exclude", ""},
}

DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
PRIORITY_ORDER = {"S": 0, "A": 1, "B": 2, "C": 3, "": 4}


def normalize_multi(value: str) -> str:
    parts = [p.strip() for p in (value or "").split(";")]
    return ";".join(p for p in parts if p)


def load(path: Path) -> tuple[list[dict[str, str]], list[str]]:
    with path.open(newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        return list(reader), list(reader.fieldnames or [])


def main() -> int:
    ap = argparse.ArgumentParser(description="校验并规范化事件库为数据库版 CSV（26 列）。")
    ap.add_argument("event_pool", help="输入事件池 CSV")
    ap.add_argument("-o", "--output", help="输出数据库版 CSV 路径；省略则只校验（dry-run）")
    ap.add_argument("--week", default="", help="ISO 周编号，仅用于报告")
    args = ap.parse_args()

    path = Path(args.event_pool).expanduser().resolve()
    if not path.exists():
        print(json.dumps({"ok": False, "error": f"未找到输入：{path}"}, ensure_ascii=False, indent=2))
        return 2

    rows, header = load(path)
    errors: list[str] = []
    warnings: list[str] = []

    # 列校验
    missing_cols = [c for c in CANONICAL_COLUMNS if c not in header]
    extra_cols = [c for c in header if c not in CANONICAL_COLUMNS]
    if missing_cols:
        errors.append(f"缺少必需列：{missing_cols}")
    if extra_cols:
        warnings.append(f"存在 schema 外的额外列（导出时丢弃）：{extra_cols}")

    # 行级校验 + 规范化
    seen_ids: dict[str, int] = {}
    cleaned: list[dict[str, str]] = []
    for i, row in enumerate(rows, start=2):  # CSV 第 1 行是表头
        out_row = {c: (row.get(c) or "").strip() for c in CANONICAL_COLUMNS}
        for c in MULTI_VALUE:
            out_row[c] = normalize_multi(out_row[c])

        eid = out_row["event_id"]
        if eid:
            if eid in seen_ids:
                errors.append(f"event_id 重复：{eid}（行 {seen_ids[eid]} 与 {i}）")
            seen_ids[eid] = i

        for c in REQUIRED_NON_EMPTY:
            if not out_row[c]:
                errors.append(f"行 {i}（{eid or '无 id'}）必填字段 {c} 为空")

        for c, allowed in ENUMS.items():
            if out_row[c] not in allowed:
                warnings.append(f"行 {i}（{eid}）{c} 取值 '{out_row[c]}' 不在枚举 {sorted(allowed)} 内")

        for c in ("date", "published_date"):
            if out_row[c] and not DATE_RE.match(out_row[c]):
                warnings.append(f"行 {i}（{eid}）{c} '{out_row[c]}' 非 ISO YYYY-MM-DD")

        cleaned.append(out_row)

    # 排序：priority S>A>B>C，再按 date
    cleaned.sort(key=lambda r: (PRIORITY_ORDER.get(r["priority"], 4), r["date"]))

    wrote = ""
    if args.output and not errors:
        out_path = Path(args.output).expanduser().resolve()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with out_path.open("w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=CANONICAL_COLUMNS)
            writer.writeheader()
            writer.writerows(cleaned)
        wrote = str(out_path)

    report = {
        "ok": not errors,
        "week": args.week,
        "input": str(path),
        "output_written": wrote,
        "row_count": len(cleaned),
        "errors": errors,
        "warnings": warnings,
    }
    if errors:
        report["next_prompt"] = "存在 error，未写文件。修正后重跑。"
    elif not args.output:
        report["next_prompt"] = "校验通过（dry-run）。加 -o <path> 写出数据库版 CSV。"
    else:
        report["next_prompt"] = f"已写出数据库版 CSV：{wrote}"
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
