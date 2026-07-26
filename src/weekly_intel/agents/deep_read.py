from __future__ import annotations

import sqlite3
import uuid
import json

from ..analysis_backend import AnalysisBackend
from ..utils import isoformat, utc_now


class PaperDeepReadAgent:
    name = "PaperDeepReadAgent"

    def __init__(self, backend: AnalysisBackend):
        self.backend = backend

    def run(self, connection: sqlite3.Connection, issue_id: str) -> int:
        rows = connection.execute(
            """
            SELECT s.selection_id, s.item_id, s.content_role,
                   s.department_implication, r.canonical_title,
                   r.abstract_or_summary, r.canonical_url,
                   a.rationale AS assessment_rationale,
                   v.raw_document_id,
                   COALESCE(
                       (
                           SELECT pc.content_text
                           FROM paper_contents pc
                           WHERE pc.item_id=r.item_id
                           ORDER BY pc.fetched_at DESC
                           LIMIT 1
                       ),
                       d.content_text
                   ) AS content_text,
                   (
                       SELECT claim_text FROM evidence_claims ep
                       WHERE ep.item_id=r.item_id
                         AND ep.claim_type='publication_status'
                       ORDER BY ep.created_at DESC LIMIT 1
                   ) AS publication_status
            FROM weekly_selections s
            JOIN research_items r ON r.item_id=s.item_id
            LEFT JOIN department_assessments a
              ON a.assessment_id=s.assessment_id
            LEFT JOIN item_versions v
              ON v.item_id=r.item_id AND v.created_at=(
                  SELECT MAX(v2.created_at) FROM item_versions v2
                  WHERE v2.item_id=r.item_id
              )
            LEFT JOIN raw_documents d
              ON d.raw_document_id=v.raw_document_id
            WHERE s.issue_id=?
              AND s.content_role IN ('must_read', 'deep_read', 'library_review')
            ORDER BY s.section, s.position
            """,
            (issue_id,),
        ).fetchall()
        completed = 0
        now = isoformat(utc_now())
        for row in rows:
            result = self.backend.deep_read(
                {
                    "title": row["canonical_title"],
                    "url": row["canonical_url"],
                    "summary": row["abstract_or_summary"],
                    "content": (row["content_text"] or "")[:12000],
                    "publication_status": row["publication_status"],
                    "assessment_rationale": row["assessment_rationale"],
                }
            )
            contribution_text = "；".join(result.contributions)
            evidence_text = "；".join(result.evidence)
            limitation_text = "；".join(result.limitations)
            display = (
                f"**中文题名：** {result.title_zh}\n\n"
                f"**{result.summary_zh}**\n\n"
                f"{result.problem_zh}\n\n"
                f"{result.method_zh}\n\n"
                f"{result.result_zh}\n\n"
                f"主要贡献：{contribution_text}\n\n"
                f"证据：{evidence_text}\n\n"
                f"局限：{limitation_text}"
            )
            connection.execute(
                """
                UPDATE weekly_selections
                SET display_summary=?, department_implication=?
                WHERE selection_id=?
                """,
                (
                    display,
                    result.department_implication,
                    row["selection_id"],
                ),
            )
            connection.execute(
                """
                INSERT INTO deep_read_cards (
                    selection_id, title_zh, one_sentence_zh, problem_zh,
                    method_zh, result_zh, contributions_json, evidence_json,
                    limitations_json, department_implication, confidence,
                    model_version, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(selection_id) DO UPDATE SET
                    title_zh=excluded.title_zh,
                    one_sentence_zh=excluded.one_sentence_zh,
                    problem_zh=excluded.problem_zh,
                    method_zh=excluded.method_zh,
                    result_zh=excluded.result_zh,
                    contributions_json=excluded.contributions_json,
                    evidence_json=excluded.evidence_json,
                    limitations_json=excluded.limitations_json,
                    department_implication=excluded.department_implication,
                    confidence=excluded.confidence,
                    model_version=excluded.model_version,
                    updated_at=excluded.updated_at
                """,
                (
                    row["selection_id"],
                    result.title_zh,
                    result.summary_zh,
                    result.problem_zh,
                    result.method_zh,
                    result.result_zh,
                    json.dumps(result.contributions, ensure_ascii=False),
                    json.dumps(result.evidence, ensure_ascii=False),
                    json.dumps(result.limitations, ensure_ascii=False),
                    result.department_implication,
                    result.confidence,
                    result.model_version,
                    now,
                    now,
                ),
            )
            if row["raw_document_id"]:
                for claim_type, texts in (
                    ("interpretation", result.contributions),
                    ("limitation", result.limitations),
                ):
                    for text in texts:
                        exists = connection.execute(
                            """
                            SELECT 1 FROM evidence_claims
                            WHERE item_id=? AND raw_document_id=?
                              AND claim_type=? AND claim_text=?
                            """,
                            (
                                row["item_id"],
                                row["raw_document_id"],
                                claim_type,
                                text,
                            ),
                        ).fetchone()
                        if exists:
                            continue
                        connection.execute(
                            """
                            INSERT INTO evidence_claims (
                                claim_id, item_id, raw_document_id, claim_type,
                                claim_text, evidence_url, evidence_tier,
                                extraction_method, confidence, human_verified,
                                created_at
                            ) VALUES (?, ?, ?, ?, ?, ?, 'primary', 'llm',
                                      ?, 0, ?)
                            """,
                            (
                                str(uuid.uuid4()),
                                row["item_id"],
                                row["raw_document_id"],
                                claim_type,
                                text,
                                row["canonical_url"],
                                result.confidence,
                                now,
                            ),
                        )
            completed += 1
        return completed
