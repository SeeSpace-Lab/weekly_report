#!/usr/bin/env python3
"""确定性核算阶段 2 / 阶段 4 的阈值 gate JSON。

SKILL.md 把阶段 2 Definition-of-Done JSON 与阶段 4 Review Gate JSON 的阈值
判断交给 agent 自报，并把"把 false 粉饰成 true"列为严重违规。本脚本改为从
事件库 CSV 直接核算这些计数，消除自报偏差——agent / 人只需把脚本输出贴进
gate，无需口算，也无法粉饰。

本脚本是纯计数，不做任何相关性 / 同心圆 / 主航道判断（那是阶段 4 评分的事，
属人工判断范畴）。它只回答"在当前事件库里，各板块各等级各有多少条、是否过线"。

用法：
    compute_gates.py <event_database.csv> --week 2026-W20 \
        [--stage 2|4|all] [--candidate-count N] \
        [--domestic-total N --domestic-kept N --overseas-total N --overseas-kept N] \
        [--time-window-excluded N]

无法从事件库本身推导的字段（candidate_count、time_window_excluded、手工融资
原表条数）通过参数传入；未提供时输出 null 并在 notes 中标明"需人工补"。
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path


# ---- 枚举归一 -------------------------------------------------------------

COUNTRY_CN = {"china", "cn", "中国", "中"}
COUNTRY_US = {"us", "usa", "united states", "美国", "美"}

SECTOR_POLICY = {"policy", "政策"}
SECTOR_TECH = {"technology", "tech", "科技"}
SECTOR_FIN = {"financing", "finance", "融资"}

# 正文（完整版前四章）口径：进正文 = include_in_report ∈ {Yes, Brief}
MAIN_TEXT_INCLUDE = {"yes", "brief"}

# 融资子板块（5C.1/5C.2/5C.3）单桶归属优先级：芯片 > 商业航天 > AI算力。
# 多 domain 的融资事件按此优先级落入唯一一个子板块，与 output-template 的
# "一条融资事件进且仅进一个 5C.x"一致。规则透明、可复核。
FIN_CHIP_DOMAINS = {"chip", "semiconductor", "芯片", "半导体"}
FIN_SPACE_DOMAINS = {"commercial_space", "satellite", "launch", "商业航天", "卫星"}
FIN_AI_DOMAINS = {"ai", "space_compute", "data_center", "ai算力", "算力"}


def norm(s: str) -> str:
    return (s or "").strip().lower()


def country_bucket(v: str) -> str:
    n = norm(v)
    if n in COUNTRY_CN:
        return "CN"
    if n in COUNTRY_US:
        return "US"
    return "OTHER"


def sector_bucket(v: str) -> str:
    n = norm(v)
    if n in SECTOR_POLICY:
        return "policy"
    if n in SECTOR_TECH:
        return "tech"
    if n in SECTOR_FIN:
        return "financing"
    return "other"


def domains(v: str) -> list[str]:
    return [norm(d) for d in (v or "").split(";") if d.strip()]


def fin_subsection(domain_list: list[str]) -> str:
    ds = set(domain_list)
    if ds & FIN_CHIP_DOMAINS:
        return "fin_chip"
    if ds & FIN_SPACE_DOMAINS:
        return "fin_space"
    if ds & FIN_AI_DOMAINS:
        return "fin_ai"
    return "fin_other"


# ---- 读事件库 -------------------------------------------------------------

def read_events(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def is_main_text(row: dict[str, str]) -> bool:
    return norm(row.get("include_in_report")) in MAIN_TEXT_INCLUDE


def scoring_done(rows: list[dict[str, str]]) -> bool:
    """include_in_report 全空 → 阶段 4 评分尚未进行。"""
    return any(norm(r.get("include_in_report")) for r in rows)


# ---- 阶段 2 ---------------------------------------------------------------

def stage2(rows: list[dict[str, str]], week: str, args: argparse.Namespace) -> dict:
    tier_dist = {"S_Core": 0, "A_Active": 0, "Watch": 0, "Backup": 0, "Manual": 0}
    for r in rows:
        t = (r.get("source_tier") or "").strip()
        if t in tier_dist:
            tier_dist[t] += 1
    pool = len(rows)
    candidate = args.candidate_count
    fin = {
        "domestic_total": args.domestic_total,
        "domestic_kept": args.domestic_kept,
        "overseas_total": args.overseas_total,
        "overseas_kept": args.overseas_kept,
    }
    notes = []
    if candidate is None:
        notes.append("candidate_count 需人工补（Pass A+B 合并去重后的候选 URL 数，不在事件库内）")
    if args.time_window_excluded is None:
        notes.append("time_window_excluded_count 需人工补（窗口外剔除数，不在最终事件库内）")
    if any(v is None for v in fin.values()):
        notes.append("manual_financing_imported 部分字段需人工补（手工融资原表条数）")
    return {
        "stage": "2_event_pool_done",
        "week": week,
        "candidate_count": candidate,
        "event_pool_count": pool,
        "time_window_excluded_count": args.time_window_excluded,
        "manual_financing_imported": fin,
        "source_tier_distribution": tier_dist,
        "thresholds_check": {
            "event_pool_ge_80": pool >= 80,
            "candidate_ge_80": (candidate >= 80) if candidate is not None else None,
        },
        "computed_by": "scripts/compute_gates.py",
        "notes": notes,
    }


# ---- 阶段 4 ---------------------------------------------------------------

def stage4(rows: list[dict[str, str]], week: str) -> dict:
    if not scoring_done(rows):
        return {
            "stage": "4_review_gate",
            "week": week,
            "computed_by": "scripts/compute_gates.py",
            "error": "include_in_report 全为空——阶段 4 评分尚未进行，无法核算正文 gate。先完成评分再跑本脚本。",
        }

    pr = {"S": 0, "A": 0, "B": 0, "C": 0}
    for r in rows:
        p = (r.get("priority") or "").strip().upper()
        if p in pr:
            pr[p] += 1

    main = [r for r in rows if is_main_text(r)]
    sub = {
        "policy_cn": 0, "policy_us": 0,
        "tech_cn": 0, "tech_us": 0, "tech_global": 0,
        "fin_chip": 0, "fin_space": 0, "fin_ai": 0, "fin_other": 0,
    }
    fin_in_main = 0
    for r in main:
        sec = sector_bucket(r.get("sector"))
        cty = country_bucket(r.get("country"))
        if sec == "policy":
            if cty == "CN":
                sub["policy_cn"] += 1
            elif cty == "US":
                sub["policy_us"] += 1
        elif sec == "tech":
            if cty == "CN":
                sub["tech_cn"] += 1
            elif cty == "US":
                sub["tech_us"] += 1
            else:
                sub["tech_global"] += 1
        elif sec == "financing":
            fin_in_main += 1
            sub[fin_subsection(domains(r.get("domain")))] += 1

    main_n = len(main)
    fin_ratio = (fin_in_main / main_n) if main_n else 0.0
    policy_total = sub["policy_cn"] + sub["policy_us"]
    tech_total = sub["tech_cn"] + sub["tech_us"] + sub["tech_global"]
    fin_total = sub["fin_chip"] + sub["fin_space"] + sub["fin_ai"]

    checks = {
        "main_text_ge_70": main_n >= 70,
        "financing_ratio_le_30": fin_ratio <= 0.30,
        "policy_ge_14": policy_total >= 14,
        "policy_cn_ge_7": sub["policy_cn"] >= 7,
        "policy_us_ge_7": sub["policy_us"] >= 7,
        "tech_ge_13": tech_total >= 13,
        "tech_cn_ge_5": sub["tech_cn"] >= 5,
        "tech_us_ge_7": sub["tech_us"] >= 7,
        "tech_global_ge_1": sub["tech_global"] >= 1,
        "financing_ge_18": fin_total >= 18,
        "fin_chip_ge_10": sub["fin_chip"] >= 10,
        "fin_space_ge_5": sub["fin_space"] >= 5,
        "fin_ai_ge_3": sub["fin_ai"] >= 3,
    }
    notes = []
    if sub["fin_other"]:
        notes.append(
            f"{sub['fin_other']} 条进正文的融资事件 domain 未落入 芯片/商业航天/AI算力 任一桶，"
            "请检查 domain 字段是否规范（未计入任何 fin_* 下限）"
        )
    return {
        "stage": "4_review_gate",
        "week": week,
        "s_count": pr["S"], "a_count": pr["A"], "b_count": pr["B"], "c_count": pr["C"],
        "main_text_count": main_n,
        "financing_in_main_count": fin_in_main,
        "financing_ratio": f"{fin_ratio * 100:.1f}%",
        "thresholds_check": checks,
        "subsection_counts": {k: v for k, v in sub.items() if k != "fin_other"},
        "all_pass": all(checks.values()),
        "computed_by": "scripts/compute_gates.py",
        "notes": notes,
        "awaiting": "user_signoff_or_adjust",
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="确定性核算阶段 2 / 阶段 4 阈值 gate JSON。")
    ap.add_argument("event_db", help="事件库 CSV 路径（26 列）")
    ap.add_argument("--week", required=True, help="ISO 周编号，如 2026-W20")
    ap.add_argument("--stage", choices=["2", "4", "all"], default="all")
    ap.add_argument("--candidate-count", type=int, default=None)
    ap.add_argument("--time-window-excluded", type=int, default=None)
    ap.add_argument("--domestic-total", type=int, default=None)
    ap.add_argument("--domestic-kept", type=int, default=None)
    ap.add_argument("--overseas-total", type=int, default=None)
    ap.add_argument("--overseas-kept", type=int, default=None)
    args = ap.parse_args()

    path = Path(args.event_db).expanduser().resolve()
    if not path.exists():
        print(json.dumps({"error": f"未找到事件库：{path}"}, ensure_ascii=False, indent=2))
        return 2
    rows = read_events(path)

    out: dict = {}
    if args.stage in ("2", "all"):
        out["stage2"] = stage2(rows, args.week, args)
    if args.stage in ("4", "all"):
        out["stage4"] = stage4(rows, args.week)
    result = out[f"stage{args.stage}"] if args.stage in ("2", "4") else out
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
