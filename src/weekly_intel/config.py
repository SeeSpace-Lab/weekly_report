from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from .contracts import SourceConfig


SOURCE_FIELDS = {
    "source_id",
    "name",
    "source_type",
    "connector",
    "tier",
    "homepage_url",
    "enabled",
}


def load_yaml(path: str | Path) -> dict[str, Any]:
    with Path(path).open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a YAML mapping")
    return data


def load_sources(path: str | Path) -> dict[str, SourceConfig]:
    data = load_yaml(path)
    result: dict[str, SourceConfig] = {}
    for entry in data.get("sources", []):
        options = {k: v for k, v in entry.items() if k not in SOURCE_FIELDS}
        source = SourceConfig(
            source_id=entry["source_id"],
            name=entry["name"],
            source_type=entry["source_type"],
            connector=entry["connector"],
            tier=entry["tier"],
            homepage_url=entry.get("homepage_url"),
            enabled=entry.get("enabled", True),
            options=options,
        )
        if source.source_id in result:
            raise ValueError(f"duplicate source_id: {source.source_id}")
        result[source.source_id] = source
    return result
