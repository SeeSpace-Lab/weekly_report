#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path


SOURCE_MAP_NAMES = {
    "source_map.csv",
}

EVENT_DB_NAMES = {
    "event_database.csv",
    "event_database.xlsx",
}

FINANCING_BASE_KEYWORDS = [
    "企查查",
    "融资",
    "工商",
    "股东",
    "qcc",
    "financing",
    "funding",
    "shareholder",
]

DOMESTIC_KEYWORDS = ["境内", "domestic"]
OVERSEAS_KEYWORDS = ["境外", "海外", "overseas", "global", "foreign"]

REPORT_KEYWORDS = [
    "周报",
    "weekly",
    "report",
    "简报",
]

REFERENCE_DOC_NAMES = {
    "weekly-system-workflow.md",
    "reporting-playbook.md",
    "output-template.md",
    "source_map_rules.md",
    "event_database_template.csv",
    "manual_financing_import_template.csv",
}

DATA_EXTS = {".csv", ".xlsx", ".xls", ".tsv"}
REPORT_EXTS = {".md", ".docx", ".pdf"}

# 国内轨中文搜索 MCP（双轨检索的国内轨）。名称命中其一即视为已安装。
CN_SEARCH_MCP_HINTS = ["bocha", "博查"]


class ChineseArgumentParser(argparse.ArgumentParser):
    def format_help(self) -> str:
        return super().format_help().replace("usage:", "用法：")


def _scan_mcp_server_names(obj):
    """递归在配置对象里找所有 mcpServers 字典，yield 其中的 server 名称。"""
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k == "mcpServers" and isinstance(v, dict):
                for name in v.keys():
                    yield name
            else:
                yield from _scan_mcp_server_names(v)
    elif isinstance(obj, list):
        for it in obj:
            yield from _scan_mcp_server_names(it)


def detect_cn_search_mcp(root: Path) -> dict:
    """检测是否安装了国内轨中文搜索 MCP（如 bocha 博查）。
    扫描 ~/.claude.json（user/project scope）、<本周文件夹>/.mcp.json、当前目录/.mcp.json。
    仅按 server 名称判断"是否安装"，不做健康检查（不连接、不读密钥）。"""
    config_paths = [Path.home() / ".claude.json", root / ".mcp.json", Path.cwd() / ".mcp.json"]
    seen, found_name = set(), None
    for cp in config_paths:
        try:
            rp = cp.resolve()
        except OSError:
            continue
        if rp in seen or not cp.exists():
            continue
        seen.add(rp)
        try:
            data = json.loads(cp.read_text(encoding="utf-8"))
        except Exception:
            continue
        for name in _scan_mcp_server_names(data):
            if any(h.lower() in name.lower() for h in CN_SEARCH_MCP_HINTS):
                found_name = name
                break
        if found_name:
            break
    return {
        "installed": found_name is not None,
        "server_name": found_name or "",
        "hint": (
            "" if found_name else
            "未检测到国内轨中文搜索 MCP（如 bocha 博查）。我的 WebSearch 为 US-only，"
            "缺它会导致中国政策/融资召回不全（CN 政策轴覆盖不足）。安装方式见 "
            "references/search-playbook.md「双轨检索」段。安装后需重开 Claude Code 才能加载该 MCP。"
        ),
    }


def list_files(root: Path) -> list[Path]:
    return [p for p in root.rglob("*") if p.is_file()]


def rel(paths: list[Path], root: Path) -> list[str]:
    return sorted(str(p.relative_to(root)) for p in paths)


def match_names(files: list[Path], names: set[str]) -> list[Path]:
    lowered = {n.lower() for n in names}
    return [p for p in files if p.name.lower() in lowered]


def match_keywords(files: list[Path], keywords: list[str], exts: set[str]) -> list[Path]:
    matches = []
    for p in files:
        if p.name in REFERENCE_DOC_NAMES:
            continue
        if p.suffix.lower() not in exts:
            continue
        name = p.name.lower()
        if any(k.lower() in name for k in keywords):
            matches.append(p)
    return matches


def split_financing_files(files: list[Path]) -> tuple[list[Path], list[Path], list[Path]]:
    """返回 (domestic, overseas, ambiguous)。ambiguous 指匹配到融资关键词但
    没有明确境内/境外标记的文件，由调用方提示用户重命名。"""
    candidates = match_keywords(files, FINANCING_BASE_KEYWORDS, DATA_EXTS)
    domestic, overseas, ambiguous = [], [], []
    for p in candidates:
        name = p.name.lower()
        is_domestic = any(k.lower() in name for k in DOMESTIC_KEYWORDS)
        is_overseas = any(k.lower() in name for k in OVERSEAS_KEYWORDS)
        if is_domestic and not is_overseas:
            domestic.append(p)
        elif is_overseas and not is_domestic:
            overseas.append(p)
        else:
            ambiguous.append(p)
    return domestic, overseas, ambiguous


def main() -> int:
    parser = ChineseArgumentParser(
        description="检查太空算力周报本周工作文件夹中的必要输入。",
        add_help=False,
        usage="check_inputs.py [-h] [--allow-missing-financing] [--require-history] 本周文件夹",
    )
    positional = parser.add_argument_group("位置参数")
    optional = parser.add_argument_group("可选参数")
    positional.add_argument("folder", metavar="本周文件夹", help="需要检查的本周工作文件夹。")
    optional.add_argument("-h", "--help", action="help", help="显示帮助信息并退出。")
    optional.add_argument("--allow-missing-financing", action="store_true", help="允许缺少企查查/融资/工商变更导入文件，仅用于公开信息草稿。")
    optional.add_argument("--require-financing", action="store_true", help=argparse.SUPPRESS)
    optional.add_argument("--require-history", action="store_true", help="将事件库或过往周报视为必要输入。")
    args = parser.parse_args()

    root = Path(args.folder).expanduser().resolve()
    if not root.exists() or not root.is_dir():
        print(json.dumps({"ok": False, "error": f"未找到文件夹：{root}"}, ensure_ascii=False, indent=2))
        return 2

    files = list_files(root)
    source_maps = match_names(files, SOURCE_MAP_NAMES)
    event_db = match_names(files, EVENT_DB_NAMES)
    domestic_financing, overseas_financing, ambiguous_financing = split_financing_files(files)
    financing = domestic_financing + overseas_financing + ambiguous_financing
    prior_reports = match_keywords(files, REPORT_KEYWORDS, REPORT_EXTS)

    required_missing = []
    optional_missing = []

    fallback_source_map = None
    if not source_maps:
        skill_root = Path(__file__).resolve().parent.parent
        candidate = skill_root / "references" / "source_map.csv"
        if candidate.exists():
            fallback_source_map = candidate
        if fallback_source_map is None:
            required_missing.append("缺少信息源地图：请提供 source_map.csv")
        else:
            optional_missing.append(
                f"本周文件夹未提供 source_map.csv，已 fallback 到 skill 内置：{fallback_source_map.relative_to(skill_root)}"
            )
    # 完整版需要境内 + 境外两个融资文件；--allow-missing-financing 才放行。
    if not args.allow_missing_financing:
        if not domestic_financing:
            required_missing.append(
                "缺少境内融资文件：文件名应包含「境内」或 domestic，并含「融资」或「企查查」等关键词（.csv/.xlsx/.tsv）"
            )
        if not overseas_financing:
            required_missing.append(
                "缺少境外融资文件：文件名应包含「境外」「海外」、overseas、global 或 foreign，并含「融资」或「企查查」等关键词（.csv/.xlsx/.tsv）"
            )
    else:
        if not domestic_financing:
            optional_missing.append("未发现境内融资文件；当前只允许生成公开信息草稿，不含境内融资模块")
        if not overseas_financing:
            optional_missing.append("未发现境外融资文件；当前只允许生成公开信息草稿，不含境外融资模块")
    if ambiguous_financing:
        optional_missing.append(
            "以下融资文件匹配到融资关键词但未标明境内/境外，请在文件名中加入「境内」或「境外」/overseas 后再跑："
            + "; ".join(str(p.relative_to(root)) for p in ambiguous_financing)
        )
    if args.require_history and not event_db and not prior_reports:
        required_missing.append("缺少历史输入：请提供 event_database.csv/.xlsx 或过往周报")
    elif not event_db:
        optional_missing.append("未发现 event_database.csv/.xlsx；如需历史去重或事件沉淀，请补充")

    # 国内轨中文搜索 MCP 检查（双轨检索）：未安装不阻塞，但必须提示。
    cn_search_mcp = detect_cn_search_mcp(root)
    if not cn_search_mcp["installed"]:
        optional_missing.append(cn_search_mcp["hint"])

    result = {
        "ok": not required_missing,
        "folder": str(root),
        "found": {
            "source_map": rel(source_maps, root),
            "source_map_fallback": str(fallback_source_map) if fallback_source_map else "",
            "manual_financing_import": rel(financing, root),
            "manual_financing_domestic": rel(domestic_financing, root),
            "manual_financing_overseas": rel(overseas_financing, root),
            "manual_financing_ambiguous": rel(ambiguous_financing, root),
            "event_database": rel(event_db, root),
            "prior_reports": rel(prior_reports, root),
        },
        "cn_search_mcp": cn_search_mcp,
        "required_missing": required_missing,
        "optional_missing": optional_missing,
        "next_prompt": "",
    }

    if required_missing:
        result["next_prompt"] = "请先补齐 required_missing 中列出的文件。缺少企查查/融资/工商变更导出时，不生成完整融资模块；若本轮只做公开信息草稿，请重新运行并加 --allow-missing-financing。"
    else:
        # 仅 fallback 到内置 source_map 不影响完整版生成；缺融资才会降级到草稿。
        domestic_ok = bool(domestic_financing)
        overseas_ok = bool(overseas_financing)
        if args.allow_missing_financing and not (domestic_ok and overseas_ok):
            missing_side = []
            if not domestic_ok:
                missing_side.append("境内")
            if not overseas_ok:
                missing_side.append("境外")
            base = (
                f"本轮跳过 {'/'.join(missing_side)} 手工融资导入，只能生成公开信息草稿"
                f"（{'/'.join(missing_side)} 融资模块缺失）。"
            )
        else:
            base = "输入文件齐备，可以进入阶段 1：生成本周扫描计划。"
        if optional_missing:
            result["next_prompt"] = base + " optional_missing 中的项不阻塞当前流程，但建议尽量补齐以提升历史去重与覆盖度。"
        else:
            result["next_prompt"] = base

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not required_missing else 1


if __name__ == "__main__":
    raise SystemExit(main())
