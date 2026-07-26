from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("database", type=Path)
    args = parser.parse_args()
    connection = sqlite3.connect(args.database)
    query = """
        SELECT COUNT(*)
        FROM item_versions v
        JOIN research_items r ON r.item_id=v.item_id
        WHERE r.item_type != 'paper'
          AND v.version_kind IN ('arxiv', 'openreview_revision')
    """
    before = connection.execute(query).fetchone()[0]
    connection.execute(
        """
        DELETE FROM item_versions
        WHERE version_id IN (
            SELECT v.version_id
            FROM item_versions v
            JOIN research_items r ON r.item_id=v.item_id
            WHERE r.item_type != 'paper'
              AND v.version_kind IN ('arxiv', 'openreview_revision')
        )
        """
    )
    connection.commit()
    after = connection.execute(query).fetchone()[0]
    connection.close()
    print(
        {
            "removed_invalid_versions": before,
            "remaining_invalid_versions": after,
        }
    )


if __name__ == "__main__":
    main()
