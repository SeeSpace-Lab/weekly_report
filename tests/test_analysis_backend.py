from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from weekly_intel.analysis_backend import (
    DeterministicAnalysisBackend,
    backend_from_environment,
)


class LocalAnalysisBackendTest(unittest.TestCase):
    def test_never_routes_to_an_external_model_api(self) -> None:
        with patch.dict(
            os.environ,
            {
                "WEEKLY_LLM_API_KEY": "must-not-be-used",
                "WEEKLY_LLM_BASE_URL": "https://example.invalid/v1",
            },
        ):
            backend = backend_from_environment()
        self.assertIsInstance(backend, DeterministicAnalysisBackend)
        result = backend.deep_read(
            {"title": "Power-aware scheduling", "summary": "abstract"}
        )
        self.assertLess(result.confidence, 0.6)
        self.assertTrue(result.model_version.startswith("deterministic"))
        self.assertIn("不可批准", result.limitations[0])


if __name__ == "__main__":
    unittest.main()
