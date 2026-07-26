from __future__ import annotations

import json
import sqlite3
import uuid
from difflib import SequenceMatcher

from ..utils import isoformat, utc_now


class VersionDiffAgent:
    name = "VersionDiffAgent"
    model_version = "deterministic-diff-v1"

    def run(self, connection: sqlite3.Connection) -> int:
        item_ids = connection.execute(
            """
            SELECT item_id FROM item_versions
            GROUP BY item_id HAVING COUNT(*) >= 2
            """
        ).fetchall()
        updated = 0
        for item_row in item_ids:
            versions = connection.execute(
                """
                SELECT v.version_id, v.version_label, v.content_hash,
                       d.title, d.summary
                FROM item_versions v
                LEFT JOIN raw_documents d
                  ON d.raw_document_id=v.raw_document_id
                WHERE v.item_id=?
                ORDER BY COALESCE(v.published_at, v.created_at)
                """,
                (item_row["item_id"],),
            ).fetchall()
            previous, latest = versions[-2], versions[-1]
            old_text = f"{previous['title'] or ''}\n{previous['summary'] or ''}"
            new_text = f"{latest['title'] or ''}\n{latest['summary'] or ''}"
            ratio = SequenceMatcher(None, old_text, new_text).ratio()
            if previous["content_hash"] == latest["content_hash"]:
                significance = "none"
            elif ratio >= 0.97:
                significance = "minor"
            elif ratio >= 0.75:
                significance = "material"
            else:
                significance = "major"
            summary = (
                f"{previous['version_label']}→{latest['version_label']}，"
                f"文本相似度{ratio:.2f}，判定为{significance}更新。"
            )
            connection.execute(
                """
                UPDATE item_versions
                SET change_significance=?, change_summary=?
                WHERE version_id=?
                """,
                (significance, summary, latest["version_id"]),
            )
            updated += 1
        return updated


class InterpretationLinkAgent:
    name = "InterpretationLinkAgent"
    model_version = "deterministic-link-v1"

    def run(self, connection: sqlite3.Connection) -> tuple[int, int]:
        rows = connection.execute(
            """
            SELECT r.item_id, r.abstract_or_summary, r.canonical_url,
                   v.raw_document_id, d.metadata_json
            FROM research_items r
            JOIN item_versions v ON v.item_id=r.item_id
            JOIN raw_documents d ON d.raw_document_id=v.raw_document_id
            WHERE r.item_type='review_article'
              AND v.created_at=(
                  SELECT MAX(v2.created_at) FROM item_versions v2
                  WHERE v2.item_id=r.item_id
              )
            """
        ).fetchall()
        claims = relations = 0
        now = isoformat(utc_now())
        for row in rows:
            if row["abstract_or_summary"]:
                exists = connection.execute(
                    """
                    SELECT 1 FROM evidence_claims
                    WHERE raw_document_id=? AND claim_type='interpretation'
                    """,
                    (row["raw_document_id"],),
                ).fetchone()
                if not exists:
                    connection.execute(
                        """
                        INSERT INTO evidence_claims (
                            claim_id, item_id, raw_document_id, claim_type,
                            claim_text, evidence_url, evidence_tier,
                            extraction_method, confidence, human_verified,
                            created_at
                        ) VALUES (?, ?, ?, 'interpretation', ?, ?,
                                  'authoritative_review', 'deterministic',
                                  0.75, 0, ?)
                        """,
                        (
                            str(uuid.uuid4()),
                            row["item_id"],
                            row["raw_document_id"],
                            row["abstract_or_summary"],
                            row["canonical_url"],
                            now,
                        ),
                    )
                    claims += 1
            metadata = json.loads(row["metadata_json"] or "{}")
            for arxiv_id in metadata.get("related_arxiv_ids", []):
                target = connection.execute(
                    """
                    SELECT item_id FROM item_identifiers
                    WHERE scheme='arxiv' AND value=?
                    """,
                    (str(arxiv_id).split("v", 1)[0],),
                ).fetchone()
                if not target:
                    continue
                cursor = connection.execute(
                    """
                    INSERT OR IGNORE INTO item_relations (
                        relation_id, from_item_id, to_item_id, relation_type,
                        evidence_raw_document_id, confidence, created_at
                    ) VALUES (?, ?, ?, 'interprets', ?, 1.0, ?)
                    """,
                    (
                        str(uuid.uuid4()),
                        row["item_id"],
                        target["item_id"],
                        row["raw_document_id"],
                        now,
                    ),
                )
                relations += int(bool(cursor.rowcount))
        return claims, relations
