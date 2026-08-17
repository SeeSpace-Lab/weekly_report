from __future__ import annotations

import json
from datetime import datetime, timezone

from weekly_intel.collectors.ieee_xplore import IeeeXploreCollector
from weekly_intel.collectors.openalex import OpenAlexCollector
from weekly_intel.contracts import BatchStatus, CollectionWindow, SourceConfig


WINDOW = CollectionWindow(
    datetime(2026, 7, 26, 16, tzinfo=timezone.utc),
    datetime(2026, 8, 2, 15, 59, tzinfo=timezone.utc),
)


def source(source_id: str, connector: str, **options: object) -> SourceConfig:
    return SourceConfig(source_id, source_id, "paper_api", connector, "S_Core", options=options)


def test_openalex_keeps_paywalled_acm_ieee_metadata(monkeypatch) -> None:
    monkeypatch.setenv("OPENALEX_API_KEY", "test-key")
    record = {
        "id": "https://openalex.org/W123",
        "display_name": "Distributed Computing in LEO Satellite Networks",
        "doi": "https://doi.org/10.1145/example",
        "publication_date": "2026-07-30",
        "updated_date": "2026-07-31",
        "primary_location": {
            "landing_page_url": "https://dl.acm.org/doi/10.1145/example",
            "source": {"display_name": "ACM MobiCom", "host_organization_name": "ACM"},
        },
        "open_access": {"is_oa": False},
        "authorships": [{"author": {"display_name": "Ada Lovelace"}}],
        "abstract_inverted_index": {"Satellite": [0], "computing": [1]},
    }
    collector = OpenAlexCollector(lambda *_: json.dumps({"results": [record], "meta": {}}).encode())
    batch = collector.collect(source("openalex", "OpenAlexCollector", search_terms=["satellite computing"], max_pages=1), WINDOW)
    assert batch.status == BatchStatus.OK
    assert batch.documents[0].metadata["access_status"] == "待获取全文｜基于摘要初筛"
    assert batch.documents[0].metadata["evidence_status"] == "abstract_screened"
    assert batch.documents[0].metadata["publisher"] == "ACM"


def test_ieee_reports_missing_key(monkeypatch) -> None:
    monkeypatch.delenv("IEEE_XPLORE_API_KEY", raising=False)
    batch = IeeeXploreCollector().collect(source("ieee_xplore", "IeeeXploreCollector"), WINDOW)
    assert batch.status == BatchStatus.BLOCKED
    assert batch.errors[0].code == "missing_api_key"


def test_openalex_reports_missing_key(monkeypatch) -> None:
    monkeypatch.delenv("OPENALEX_API_KEY", raising=False)
    batch = OpenAlexCollector().collect(source("openalex", "OpenAlexCollector"), WINDOW)
    assert batch.status == BatchStatus.BLOCKED
    assert batch.errors[0].code == "missing_api_key"
