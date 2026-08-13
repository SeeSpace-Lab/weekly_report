from __future__ import annotations

import re
from dataclasses import replace
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

DEPARTMENT_ID_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")
PAGE_SLUG_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
BUILTIN_TOPIC_IDS = {
    "inference_runtime",
    "scheduling",
    "power_aware",
    "kv_storage",
    "moe_runtime",
    "quantization",
    "reliability",
    "edge_realtime",
    "distributed_inference",
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


def department_slug(department: dict[str, Any]) -> str:
    page = department.get("page", {})
    configured = page.get("slug") if isinstance(page, dict) else None
    return str(configured or department["department_id"]).replace("_", "-")


def department_source_ids(department: dict[str, Any]) -> set[str]:
    pool = department.get("source_pool", {})
    if not isinstance(pool, dict):
        return set()
    source_ids: set[str] = set()
    for key, values in pool.items():
        if key == "overrides" or not isinstance(values, list):
            continue
        source_ids.update(str(value) for value in values)
    return source_ids


def department_source_configs(
    sources: dict[str, SourceConfig],
    department: dict[str, Any],
) -> dict[str, SourceConfig]:
    configured_ids = department_source_ids(department)
    selected_ids = configured_ids or {
        source_id
        for source_id, source in sources.items()
        if source.enabled
    }
    pool = department.get("source_pool", {})
    overrides = (
        pool.get("overrides", {})
        if isinstance(pool, dict)
        else {}
    )
    unknown = sorted(selected_ids - set(sources))
    if unknown:
        raise ValueError(
            "unknown source_id values in department source_pool: "
            + ", ".join(unknown)
        )
    selected: dict[str, SourceConfig] = {}
    for source_id in selected_ids:
        source = sources[source_id]
        override = overrides.get(source_id, {})
        if override and not isinstance(override, dict):
            raise ValueError(
                f"source override for {source_id} must be a mapping"
            )
        options = dict(source.options)
        options.update(override)
        selected[source_id] = replace(source, options=options)
    return selected


def validate_department(
    department: dict[str, Any],
    *,
    source_ids: set[str] | None = None,
    path: Path | None = None,
) -> None:
    label = str(path or department.get("department_id") or "department")
    department_id = str(department.get("department_id") or "")
    if not DEPARTMENT_ID_PATTERN.fullmatch(department_id):
        raise ValueError(
            f"{label}: department_id must match "
            f"{DEPARTMENT_ID_PATTERN.pattern}"
        )
    slug = department_slug(department)
    if not PAGE_SLUG_PATTERN.fullmatch(slug):
        raise ValueError(
            f"{label}: page.slug must match {PAGE_SLUG_PATTERN.pattern}"
        )
    for field in ("name", "version", "mission"):
        if not str(department.get(field) or "").strip():
            raise ValueError(f"{label}: {field} is required")
    enabled = department.get("enabled", True)
    if not isinstance(enabled, bool):
        raise ValueError(f"{label}: enabled must be true or false")
    if not enabled:
        return
    topics = department.get("core_topics", [])
    if not isinstance(topics, list) or not topics:
        raise ValueError(f"{label}: enabled department needs core_topics")
    topic_ids: set[str] = set()
    for topic in topics:
        if not isinstance(topic, dict) or not str(topic.get("id") or ""):
            raise ValueError(f"{label}: every core topic needs an id")
        topic_id = str(topic["id"])
        if topic_id in topic_ids:
            raise ValueError(f"{label}: duplicate core topic {topic_id}")
        topic_ids.add(topic_id)
        if not str(topic.get("label") or ""):
            raise ValueError(f"{label}: topic {topic_id} needs a label")
        if not topic.get("keywords") and topic_id not in BUILTIN_TOPIC_IDS:
            raise ValueError(
                f"{label}: custom topic {topic_id} needs keywords"
            )
        if not topic.get("section") and topic_id not in BUILTIN_TOPIC_IDS:
            raise ValueError(
                f"{label}: custom topic {topic_id} needs a section"
            )
    keywords = department.get("keywords", {})
    if not isinstance(keywords, dict) or not keywords.get("include"):
        raise ValueError(f"{label}: keywords.include cannot be empty")
    output = department.get("weekly_output", {})
    max_items = int(output.get("max_items", 8))
    min_items = int(output.get("min_items", 1))
    target_minutes = int(output.get("target_read_minutes", 30))
    if not 1 <= max_items <= 20:
        raise ValueError(f"{label}: weekly_output.max_items must be 1-20")
    if not 0 <= min_items <= max_items:
        raise ValueError(
            f"{label}: weekly_output.min_items must be 0-max_items"
        )
    if not 1 <= target_minutes <= 30:
        raise ValueError(
            f"{label}: weekly_output.target_read_minutes must be 1-30"
        )
    candidate_policy = department.get("candidate_policy", {})
    if not isinstance(candidate_policy, dict):
        raise ValueError(f"{label}: candidate_policy must be a mapping")
    allow_preprints = candidate_policy.get(
        "allow_strong_new_preprints",
        False,
    )
    if not isinstance(allow_preprints, bool):
        raise ValueError(
            f"{label}: candidate_policy.allow_strong_new_preprints "
            "must be true or false"
        )
    for field in (
        "min_strong_new_preprint_relevance",
        "min_supplemental_relevance",
        "min_codex_brief_relevance",
    ):
        value = candidate_policy.get(field)
        if value is None:
            continue
        if (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not 0 <= float(value) <= 1
        ):
            raise ValueError(
                f"{label}: candidate_policy.{field} must be between 0 and 1"
            )
    minimum_minutes = int(output.get("minimum_read_minutes", 1))
    if not 1 <= minimum_minutes <= target_minutes:
        raise ValueError(
            f"{label}: weekly_output.minimum_read_minutes must be "
            "between 1 and target_read_minutes"
        )
    read_minutes = candidate_policy.get("read_minutes", {})
    if not isinstance(read_minutes, dict) or any(
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or float(value) <= 0
        for value in read_minutes.values()
    ):
        raise ValueError(
            f"{label}: candidate_policy.read_minutes must contain "
            "positive numbers"
        )
    sections = output.get("sections", [])
    if not isinstance(sections, list) or "must_read" not in sections:
        raise ValueError(
            f"{label}: weekly_output.sections must include must_read"
        )
    missing_topic_sections = sorted(
        {
            str(topic["section"])
            for topic in topics
            if topic.get("section")
            and str(topic["section"]) not in sections
        }
    )
    if missing_topic_sections:
        raise ValueError(
            f"{label}: topic sections missing from weekly_output.sections: "
            + ", ".join(missing_topic_sections)
        )
    section_routing = output.get("section_routing", {})
    if section_routing:
        if not isinstance(section_routing, dict):
            raise ValueError(
                f"{label}: weekly_output.section_routing must be a mapping"
            )
        mapping = section_routing.get("mapping", {})
        if not isinstance(mapping, dict):
            raise ValueError(
                f"{label}: weekly_output.section_routing.mapping "
                "must be a mapping"
            )
        routed_sections = {
            str(section)
            for layer in mapping.values()
            if isinstance(layer, dict)
            for section in layer.values()
        }
        undeclared = sorted(routed_sections - set(sections))
        if undeclared:
            raise ValueError(
                f"{label}: section routing references undeclared sections: "
                + ", ".join(undeclared)
            )
    configured_sources = department_source_ids(department)
    if not configured_sources:
        raise ValueError(f"{label}: source_pool cannot be empty")
    if source_ids is not None:
        unknown = sorted(configured_sources - source_ids)
        if unknown:
            raise ValueError(
                f"{label}: unknown source ids: " + ", ".join(unknown)
            )


def load_departments(
    directory: str | Path,
    *,
    sources_path: str | Path | None = None,
) -> list[dict[str, Any]]:
    directory = Path(directory)
    known_sources = (
        set(load_sources(sources_path))
        if sources_path is not None
        else None
    )
    departments: list[dict[str, Any]] = []
    ids: set[str] = set()
    slugs: set[str] = set()
    for path in sorted(directory.glob("*.yaml")):
        if path.name.startswith("_"):
            continue
        department = load_yaml(path)
        validate_department(
            department,
            source_ids=known_sources,
            path=path,
        )
        department_id = str(department["department_id"])
        slug = department_slug(department)
        if department_id in ids:
            raise ValueError(f"duplicate department_id: {department_id}")
        if slug in slugs:
            raise ValueError(f"duplicate department page slug: {slug}")
        ids.add(department_id)
        slugs.add(slug)
        department["_config_path"] = str(path.resolve())
        departments.append(department)
    departments.sort(
        key=lambda department: (
            int(department.get("page", {}).get("order", 999)),
            str(department["department_id"]),
        )
    )
    return departments


def find_department(
    directory: str | Path,
    identifier: str,
    *,
    sources_path: str | Path | None = None,
) -> dict[str, Any]:
    for department in load_departments(
        directory,
        sources_path=sources_path,
    ):
        if identifier in {
            str(department["department_id"]),
            department_slug(department),
        }:
            return department
    raise ValueError(f"department not found: {identifier}")
