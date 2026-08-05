from __future__ import annotations

import copy
import unittest
from pathlib import Path

from weekly_intel.config import (
    department_slug,
    department_source_configs,
    department_source_ids,
    load_departments,
    load_sources,
    load_yaml,
    validate_department,
)


class DepartmentConfigTest(unittest.TestCase):
    def setUp(self) -> None:
        self.root = Path(__file__).parents[1]
        self.sources_path = self.root / "config" / "sources.yaml"
        self.department_path = (
            self.root / "config" / "departments" / "orbitinfer.yaml"
        )

    def test_loads_enabled_and_placeholder_departments(self) -> None:
        departments = load_departments(
            self.root / "config" / "departments",
            sources_path=self.sources_path,
        )
        self.assertEqual(
            {department["department_id"] for department in departments},
            {
                "orbitinfer",
                "constellation_simulation",
                "model_and_application",
            },
        )
        orbitinfer = next(
            department
            for department in departments
            if department["department_id"] == "orbitinfer"
        )
        self.assertEqual(department_slug(orbitinfer), "orbitinfer")
        self.assertIn("wechat_paperweekly", department_source_ids(orbitinfer))

    def test_department_source_overrides_are_applied(self) -> None:
        department = load_yaml(self.department_path)
        sources = department_source_configs(
            load_sources(self.sources_path),
            department,
        )
        self.assertEqual(
            set(sources),
            department_source_ids(department),
        )
        self.assertIn(
            "power aware inference",
            sources["arxiv"].options["search_terms"],
        )

    def test_rejects_unknown_department_source(self) -> None:
        department = copy.deepcopy(load_yaml(self.department_path))
        department["source_pool"]["papers"].append("missing_source")
        with self.assertRaisesRegex(ValueError, "unknown source ids"):
            validate_department(
                department,
                source_ids=set(load_sources(self.sources_path)),
            )

    def test_custom_topic_requires_keywords(self) -> None:
        department = copy.deepcopy(load_yaml(self.department_path))
        department["core_topics"] = [
            {
                "id": "custom_topic",
                "label": "Custom",
                "section": "custom_topic",
            }
        ]
        with self.assertRaisesRegex(ValueError, "needs keywords"):
            validate_department(department)

    def test_topic_section_must_be_declared_in_output(self) -> None:
        department = copy.deepcopy(load_yaml(self.department_path))
        department["core_topics"][0]["section"] = "missing_section"
        with self.assertRaisesRegex(
            ValueError,
            "topic sections missing",
        ):
            validate_department(department)


if __name__ == "__main__":
    unittest.main()
