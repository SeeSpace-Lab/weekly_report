from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..contracts import (
    BatchStatus,
    CollectionBatch,
    CollectionError,
    CollectionWindow,
    CollectedDocument,
    DocumentType,
    SourceConfig,
)
from ..utils import json_dumps, sha256_text, utc_now


def _datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(
        timezone.utc
    )


class ManualInboxCollector:
    name = "ManualInboxCollector"

    def collect(
        self,
        source: SourceConfig,
        window: CollectionWindow,
        cursor: str | None = None,
    ) -> CollectionBatch:
        run_id = str(uuid.uuid4())
        path = Path(str(source.options.get("inbox_path", "inbox/manual.jsonl")))
        if not path.exists():
            return CollectionBatch(
                run_id=run_id,
                source_id=source.source_id,
                status=BatchStatus.UNCHANGED,
                stats={"lines": 0, "in_window": 0, "path": str(path)},
            )
        documents = []
        errors = []
        lines = 0
        latest_seen = None
        for line_number, line in enumerate(
            path.read_text(encoding="utf-8").splitlines(), start=1
        ):
            if not line.strip() or line.lstrip().startswith("#"):
                continue
            lines += 1
            try:
                record: dict[str, Any] = json.loads(line)
                url = str(record["url"])
                title = str(record["title"])
                published = _datetime(record.get("published_at"))
                discovered = _datetime(record.get("submitted_at")) or utc_now()
                event_time = published or discovered
                latest_seen = max(latest_seen or event_time, event_time)
                if not window.start <= event_time <= window.end:
                    continue
                document_type = DocumentType(
                    record.get("document_type", "manual")
                )
                payload_hash = sha256_text(json_dumps(record))
                identifiers = dict(record.get("identifiers") or {})
                identifiers.setdefault("url_fingerprint", sha256_text(url))
                metadata = dict(record.get("metadata") or {})
                metadata.update(
                    {
                        "submitter": record.get("submitter"),
                        "source_account": record.get("source_account"),
                        "notes": record.get("notes"),
                        "item_title": record.get("item_title"),
                    }
                )
                documents.append(
                    CollectedDocument(
                        source_id=source.source_id,
                        external_id=str(record.get("id") or payload_hash),
                        document_type=document_type,
                        canonical_url=url,
                        title=title,
                        published_at=published,
                        updated_at_source=_datetime(record.get("updated_at")),
                        discovered_at=discovered,
                        authors=tuple(record.get("authors") or ()),
                        summary=record.get("summary"),
                        content_text=record.get("content_text"),
                        language=record.get("language", "zh"),
                        identifiers=identifiers,
                        metadata=metadata,
                        raw_payload=record,
                        content_hash=payload_hash,
                    )
                )
            except Exception as error:
                errors.append(
                    CollectionError(
                        code="invalid_inbox_record",
                        message=f"line {line_number}: {error}",
                        retryable=False,
                        target=str(path),
                    )
                )
        if errors and documents:
            status = BatchStatus.PARTIAL
        elif errors:
            status = BatchStatus.ERROR
        elif documents:
            status = BatchStatus.OK
        else:
            status = BatchStatus.UNCHANGED
        return CollectionBatch(
            run_id=run_id,
            source_id=source.source_id,
            status=status,
            documents=documents,
            next_cursor=latest_seen.isoformat() if latest_seen else cursor,
            errors=errors,
            stats={
                "lines": lines,
                "in_window": len(documents),
                "invalid": len(errors),
                "path": str(path),
            },
        )
