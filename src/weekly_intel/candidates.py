from __future__ import annotations

import json
import sqlite3
from typing import Any

from .utils import normalize_title


def rank_candidates(
    connection: sqlite3.Connection,
    department: dict[str, Any],
    limit: int = 30,
) -> list[dict[str, Any]]:
    include = department.get("keywords", {}).get("include", [])
    terms = [(term, normalize_title(str(term))) for term in include]
    rows = connection.execute(
        """
        SELECT item_id, canonical_title, abstract_or_summary, canonical_url,
               authors_json, first_published_at, latest_updated_at,
               (
                   SELECT claim_text FROM evidence_claims
                   WHERE evidence_claims.item_id = research_items.item_id
                     AND claim_type = 'publication_status'
                   ORDER BY created_at DESC LIMIT 1
               ) AS publication_status
        FROM research_items
        WHERE item_type = 'paper'
        ORDER BY latest_updated_at DESC
        """
    ).fetchall()
    results = []
    for row in rows:
        haystack = normalize_title(
            f"{row['canonical_title']} {row['abstract_or_summary'] or ''}"
        )
        matches = [original for original, term in terms if term and term in haystack]
        if not matches:
            continue
        publication_status = row["publication_status"]
        accepted = bool(
            publication_status
            and any(
                marker in publication_status.casefold()
                for marker in ("accept", "oral", "poster", "spotlight")
            )
        )
        score = min(1.0, 0.35 + 0.15 * len(matches) + (0.25 if accepted else 0))
        results.append(
            {
                "item_id": row["item_id"],
                "title": row["canonical_title"],
                "url": row["canonical_url"],
                "authors": json.loads(row["authors_json"]),
                "published_at": row["first_published_at"],
                "updated_at": row["latest_updated_at"],
                "publication_status": publication_status,
                "accepted_venue_boost": accepted,
                "keyword_score": round(score, 2),
                "matched_keywords": matches,
            }
        )
    return sorted(
        results,
        key=lambda item: (item["keyword_score"], item["updated_at"] or ""),
        reverse=True,
    )[:limit]
