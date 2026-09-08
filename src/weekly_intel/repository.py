from __future__ import annotations

import sqlite3
import uuid
from dataclasses import asdict
from datetime import datetime
from typing import Iterable

from .contracts import CollectionBatch, CollectionWindow, CollectedDocument, SourceConfig
from .utils import isoformat, json_dumps, normalize_title, utc_now


class Repository:
    def __init__(self, connection: sqlite3.Connection):
        self.connection = connection

    def upsert_source(self, source: SourceConfig) -> None:
        now = isoformat(utc_now())
        self.connection.execute(
            """
            INSERT INTO sources (
                source_id, name, source_type, connector, tier, homepage_url,
                config_json, enabled, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(source_id) DO UPDATE SET
                name=excluded.name, source_type=excluded.source_type,
                connector=excluded.connector, tier=excluded.tier,
                homepage_url=excluded.homepage_url,
                config_json=excluded.config_json, enabled=excluded.enabled,
                updated_at=excluded.updated_at
            """,
            (
                source.source_id,
                source.name,
                source.source_type,
                source.connector,
                source.tier,
                source.homepage_url,
                json_dumps(dict(source.options)),
                int(source.enabled),
                now,
                now,
            ),
        )

    def get_cursor(self, source_id: str) -> str | None:
        row = self.connection.execute(
            "SELECT cursor_value FROM source_cursors WHERE source_id = ?",
            (source_id,),
        ).fetchone()
        return row["cursor_value"] if row else None

    def start_run(
        self,
        run_id: str,
        source: SourceConfig,
        window: CollectionWindow,
        cursor: str | None,
        collector_name: str,
    ) -> None:
        self.connection.execute(
            """
            INSERT INTO collection_runs (
                run_id, source_id, collector_name, window_start, window_end,
                cursor_before, status, started_at
            ) VALUES (?, ?, ?, ?, ?, ?, 'running', ?)
            """,
            (
                run_id,
                source.source_id,
                collector_name,
                isoformat(window.start),
                isoformat(window.end),
                cursor,
                isoformat(utc_now()),
            ),
        )

    def ingest_documents(
        self, run_id: str, documents: Iterable[CollectedDocument]
    ) -> tuple[int, int]:
        created = skipped = 0
        for document in documents:
            raw_id = str(uuid.uuid4())
            cursor = self.connection.execute(
                """
                INSERT OR IGNORE INTO raw_documents (
                    raw_document_id, source_id, collection_run_id, external_id,
                    document_type, canonical_url, title, authors_json,
                    published_at, updated_at_source, discovered_at, language,
                    summary, content_text, content_html, identifiers_json,
                    metadata_json, raw_payload_json, content_hash
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    raw_id,
                    document.source_id,
                    run_id,
                    document.external_id,
                    document.document_type.value,
                    document.canonical_url,
                    document.title,
                    json_dumps(list(document.authors)),
                    isoformat(document.published_at),
                    isoformat(document.updated_at_source),
                    isoformat(document.discovered_at),
                    document.language,
                    document.summary,
                    document.content_text,
                    document.content_html,
                    json_dumps(dict(document.identifiers)),
                    json_dumps(dict(document.metadata)),
                    json_dumps(document.raw_payload)
                    if document.raw_payload is not None
                    else None,
                    document.content_hash,
                ),
            )
            if cursor.rowcount:
                created += 1
                if document.document_type.value == "paper_record":
                    self._normalize_paper(raw_id, document)
                elif document.document_type.value in {
                    "release",
                    "repository",
                    "model",
                    "dataset",
                    "benchmark",
                    "venue_event",
                    "review_article",
                    "official_blog",
                    "manual",
                }:
                    self._normalize_nonpaper(raw_id, document)
            else:
                skipped += 1
        return created, skipped

    def _normalize_paper(
        self, raw_document_id: str, document: CollectedDocument
    ) -> None:
        item_id = None
        for scheme in (
            "doi",
            "arxiv",
            "openreview_forum",
            "openalex",
            "ieee_article_number",
            "venue_paper",
        ):
            value = document.identifiers.get(scheme)
            if not value:
                continue
            row = self.connection.execute(
                """
                SELECT item_id FROM item_identifiers
                WHERE scheme = ? AND value = ?
                """,
                (scheme, value),
            ).fetchone()
            if row:
                item_id = row["item_id"]
                break
        if item_id is None:
            row = self.connection.execute(
                """
                SELECT item_id FROM research_items
                WHERE item_type = 'paper' AND normalized_title = ?
                ORDER BY created_at LIMIT 1
                """,
                (normalize_title(document.title),),
            ).fetchone()
            item_id = row["item_id"] if row else None
        now = isoformat(utc_now())
        if item_id is None:
            item_id = str(uuid.uuid4())
            self.connection.execute(
                """
                INSERT INTO research_items (
                    item_id, item_type, canonical_title, normalized_title,
                    canonical_url, abstract_or_summary, authors_json,
                    first_published_at, latest_updated_at, language,
                    created_at, updated_at
                ) VALUES (?, 'paper', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    item_id,
                    document.title,
                    normalize_title(document.title),
                    document.canonical_url,
                    document.summary,
                    json_dumps(list(document.authors)),
                    isoformat(document.published_at),
                    isoformat(document.updated_at_source or document.published_at),
                    document.language,
                    now,
                    now,
                ),
            )
        else:
            self.connection.execute(
                """
                UPDATE research_items SET canonical_title=?, normalized_title=?,
                    canonical_url=?, abstract_or_summary=?, authors_json=?,
                    latest_updated_at=?, updated_at=?
                WHERE item_id=?
                """,
                (
                    document.title,
                    normalize_title(document.title),
                    document.canonical_url,
                    document.summary,
                    json_dumps(list(document.authors)),
                    isoformat(document.updated_at_source or document.published_at),
                    now,
                    item_id,
                ),
            )
        for scheme, value in document.identifiers.items():
            if scheme not in {
                "doi",
                "arxiv",
                "openreview_forum",
                "openalex",
                "ieee_article_number",
                "github",
                "huggingface",
                "venue_paper",
                "url_fingerprint",
                "other",
            }:
                continue
            self.connection.execute(
                """
                INSERT OR IGNORE INTO item_identifiers (
                    identifier_id, item_id, scheme, value, is_primary, created_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    str(uuid.uuid4()),
                    item_id,
                    scheme,
                    value,
                    int(
                        scheme == "arxiv"
                        or (
                            scheme == "openreview_forum"
                            and "arxiv" not in document.identifiers
                        )
                    ),
                    now,
                ),
            )

        version_label = str(document.metadata.get("version", "v1"))
        version_number = None
        if version_label.startswith("v") and version_label[1:].isdigit():
            version_number = int(version_label[1:])
        version_kind = (
            "openreview_revision"
            if "openreview_forum" in document.identifiers
            else (
                "arxiv"
                if "arxiv" in document.identifiers
                else "other"
            )
        )
        self.connection.execute(
            """
            INSERT OR IGNORE INTO item_versions (
                version_id, item_id, raw_document_id, version_kind,
                version_label, version_number, published_at, canonical_url,
                content_hash, change_significance, metadata_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'unknown', ?, ?)
            """,
            (
                str(uuid.uuid4()),
                item_id,
                raw_document_id,
                version_kind,
                version_label,
                version_number,
                isoformat(document.updated_at_source or document.published_at),
                document.canonical_url,
                document.content_hash,
                json_dumps(dict(document.metadata)),
                now,
            ),
        )
        venue_status = document.metadata.get("venue_status")
        if venue_status:
            self.connection.execute(
                """
                INSERT INTO evidence_claims (
                    claim_id, item_id, raw_document_id, claim_type,
                    claim_text, evidence_url, evidence_tier,
                    extraction_method, confidence, human_verified, created_at
                ) VALUES (?, ?, ?, 'publication_status', ?, ?, 'primary',
                          'deterministic', 1.0, 0, ?)
                """,
                (
                    str(uuid.uuid4()),
                    item_id,
                    raw_document_id,
                    f"OpenReview venue status: {venue_status}",
                    document.canonical_url,
                    now,
                ),
            )

    def _normalize_nonpaper(
        self, raw_document_id: str, document: CollectedDocument
    ) -> None:
        item_type = {
            "release": "framework",
            "repository": "framework",
            "model": "framework",
            "dataset": "dataset",
            "benchmark": "benchmark",
            "venue_event": "venue_event",
            "review_article": "review_article",
            "official_blog": "industry_update",
            "manual": "industry_update",
        }[document.document_type.value]
        item_id = None
        for scheme in ("github", "huggingface", "url_fingerprint"):
            value = document.identifiers.get(scheme)
            if not value:
                continue
            row = self.connection.execute(
                "SELECT item_id FROM item_identifiers WHERE scheme=? AND value=?",
                (scheme, value),
            ).fetchone()
            if row:
                item_id = row["item_id"]
                break
        item_title = str(document.metadata.get("item_title") or document.title)
        normalized = normalize_title(item_title)
        if item_id is None:
            row = self.connection.execute(
                """
                SELECT item_id FROM research_items
                WHERE item_type=? AND normalized_title=?
                ORDER BY created_at LIMIT 1
                """,
                (item_type, normalized),
            ).fetchone()
            item_id = row["item_id"] if row else None
        now = isoformat(utc_now())
        if item_id is None:
            item_id = str(uuid.uuid4())
            self.connection.execute(
                """
                INSERT INTO research_items (
                    item_id, item_type, canonical_title, normalized_title,
                    canonical_url, abstract_or_summary, authors_json,
                    first_published_at, latest_updated_at, language,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    item_id,
                    item_type,
                    item_title,
                    normalized,
                    document.canonical_url,
                    document.summary,
                    json_dumps(list(document.authors)),
                    isoformat(document.published_at),
                    isoformat(document.updated_at_source or document.published_at),
                    document.language,
                    now,
                    now,
                ),
            )
        else:
            self.connection.execute(
                """
                UPDATE research_items SET abstract_or_summary=?,
                    canonical_url=?, latest_updated_at=?, updated_at=?
                WHERE item_id=?
                """,
                (
                    document.summary,
                    document.canonical_url,
                    isoformat(document.updated_at_source or document.published_at),
                    now,
                    item_id,
                ),
            )
        for scheme, value in document.identifiers.items():
            if scheme not in {
                "doi", "arxiv", "openreview_forum", "github", "huggingface",
                "venue_paper", "url_fingerprint", "other",
            }:
                continue
            self.connection.execute(
                """
                INSERT OR IGNORE INTO item_identifiers (
                    identifier_id, item_id, scheme, value, is_primary, created_at
                ) VALUES (?, ?, ?, ?, 1, ?)
                """,
                (str(uuid.uuid4()), item_id, scheme, value, now),
            )
        version_kind = (
            "release"
            if document.document_type.value == "release"
            else "web_revision"
        )
        version_label = str(
            document.metadata.get("version")
            or document.external_id
            or document.content_hash[:12]
        )
        self.connection.execute(
            """
            INSERT OR IGNORE INTO item_versions (
                version_id, item_id, raw_document_id, version_kind,
                version_label, published_at, canonical_url, content_hash,
                change_significance, metadata_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'unknown', ?, ?)
            """,
            (
                str(uuid.uuid4()),
                item_id,
                raw_document_id,
                version_kind,
                version_label,
                isoformat(document.updated_at_source or document.published_at),
                document.canonical_url,
                document.content_hash,
                json_dumps(dict(document.metadata)),
                now,
            ),
        )
        if document.document_type.value in {
            "release", "model", "dataset", "benchmark"
        }:
            status_text = (
                f"Official release: {version_label}"
                if document.document_type.value == "release"
                else f"Official {document.document_type.value} update: {version_label}"
            )
            self.connection.execute(
                """
                INSERT INTO evidence_claims (
                    claim_id, item_id, raw_document_id, claim_type, claim_text,
                    evidence_url, evidence_tier, extraction_method, confidence,
                    human_verified, created_at
                ) VALUES (?, ?, ?, 'release_status', ?, ?, 'official',
                          'deterministic', 1.0, 0, ?)
                """,
                (
                    str(uuid.uuid4()),
                    item_id,
                    raw_document_id,
                    status_text,
                    document.canonical_url,
                    now,
                ),
            )
        elif document.document_type.value == "venue_event":
            self.connection.execute(
                """
                INSERT INTO evidence_claims (
                    claim_id, item_id, raw_document_id, claim_type, claim_text,
                    evidence_url, evidence_tier, extraction_method, confidence,
                    human_verified, created_at
                ) VALUES (?, ?, ?, 'fact', ?, ?, 'official',
                          'deterministic', 1.0, 0, ?)
                """,
                (
                    str(uuid.uuid4()),
                    item_id,
                    raw_document_id,
                    "Official venue page snapshot updated",
                    document.canonical_url,
                    now,
                ),
            )

    def finish_run(
        self,
        batch: CollectionBatch,
        created: int,
        skipped: int,
    ) -> None:
        self.connection.execute(
            """
            UPDATE collection_runs SET cursor_after=?, status=?,
                fetched_count=?, created_count=?, skipped_count=?,
                failed_count=?, finished_at=?, error_json=?, stats_json=?
            WHERE run_id=?
            """,
            (
                batch.next_cursor,
                batch.status.value,
                len(batch.documents),
                created,
                skipped,
                len(batch.errors),
                isoformat(utc_now()),
                json_dumps([asdict(error) for error in batch.errors])
                if batch.errors
                else None,
                json_dumps(dict(batch.stats)),
                batch.run_id,
            ),
        )
        if batch.status.value in {"ok", "unchanged", "partial"}:
            self.connection.execute(
                """
                INSERT INTO source_cursors (
                    source_id, cursor_value, last_successful_run_id, updated_at
                ) VALUES (?, ?, ?, ?)
                ON CONFLICT(source_id) DO UPDATE SET
                    cursor_value=excluded.cursor_value,
                    last_successful_run_id=excluded.last_successful_run_id,
                    updated_at=excluded.updated_at
                """,
                (
                    batch.source_id,
                    batch.next_cursor,
                    batch.run_id,
                    isoformat(utc_now()),
                ),
            )
