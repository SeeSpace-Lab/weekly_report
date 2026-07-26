#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import re
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit


URL_RE = re.compile(r"`(https?://[^`]+)`")
CURATED_LIST_HEADING = "强制扫描的栏目主页策展清单"
CURATED_LIST_END = "WebFetch 用法"


def normalize_url(url: str) -> str:
    parts = urlsplit(url.strip())
    scheme = parts.scheme.lower()
    netloc = parts.netloc.lower()
    path = parts.path.rstrip("/") or "/"
    return urlunsplit((scheme, netloc, path, parts.query, ""))


def add_url(
    rows: list[dict[str, str]],
    seen: set[str],
    url: str,
    source: str,
    source_id: str = "",
    source_name: str = "",
) -> None:
    url = url.strip()
    if not url.lower().startswith(("http://", "https://")):
        return
    key = normalize_url(url)
    if key in seen:
        for row in rows:
            if row["normalized_url"] == key and source not in row["required_by"]:
                row["required_by"] += f";{source}"
                if source_id and source_id not in row["source_ids"]:
                    row["source_ids"] = ";".join(filter(None, [row["source_ids"], source_id]))
                break
        return
    seen.add(key)
    rows.append(
        {
            "url": url,
            "normalized_url": key,
            "required_by": source,
            "source_id": source_id,
            "source_name": source_name,
            "source_ids": source_id,
        }
    )


def extract_curated_urls(playbook: Path) -> list[str]:
    lines = playbook.read_text(encoding="utf-8").splitlines()
    in_list = False
    urls: list[str] = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith(CURATED_LIST_HEADING):
            in_list = True
            continue
        if in_list and stripped.startswith(CURATED_LIST_END):
            break
        if in_list:
            match = URL_RE.search(line)
            if match:
                urls.append(match.group(1))
    return urls


def extract_s_core_urls(source_map: Path) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    rows: list[dict[str, str]] = []
    skipped: list[dict[str, str]] = []
    with source_map.open(newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if (row.get("tier") or "").strip() != "S_Core":
                continue
            url = (row.get("url") or "").strip()
            item = {
                "source_id": (row.get("source_id") or "").strip(),
                "source_name": (row.get("source_name") or "").strip(),
                "url": url,
            }
            if url.lower().startswith(("http://", "https://")):
                rows.append(item)
            else:
                skipped.append(item)
    return rows, skipped


def main() -> int:
    skill_root = Path(__file__).resolve().parent.parent
    parser = argparse.ArgumentParser(
        description="Build the Pass B required WebFetch URL set from the curated playbook list and source_map S_Core URLs."
    )
    parser.add_argument("--playbook", default=str(skill_root / "references" / "search-playbook.md"))
    parser.add_argument("--source-map", default=str(skill_root / "references" / "source_map.csv"))
    args = parser.parse_args()

    playbook = Path(args.playbook).expanduser().resolve()
    source_map = Path(args.source_map).expanduser().resolve()

    required: list[dict[str, str]] = []
    seen: set[str] = set()

    curated_urls = extract_curated_urls(playbook)
    if not curated_urls:
        raise SystemExit(
            f"ERROR: No curated Pass B URLs found in {playbook}. "
            f"Expected a section heading starting with '{CURATED_LIST_HEADING}'."
        )
    for url in curated_urls:
        add_url(required, seen, url, "curated_pass_b")

    s_core_urls, skipped_s_core = extract_s_core_urls(source_map)
    for row in s_core_urls:
        add_url(
            required,
            seen,
            row["url"],
            "source_map_s_core",
            row["source_id"],
            row["source_name"],
        )

    result = {
        "pass_b_total_required": len(required),
        "curated_pass_b_url_count": len(curated_urls),
        "source_map_s_core_url_count": len(s_core_urls),
        "source_map_s_core_skipped_count": len(skipped_s_core),
        "source_map_s_core_skipped": skipped_s_core,
        "pass_b_required_urls": required,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
