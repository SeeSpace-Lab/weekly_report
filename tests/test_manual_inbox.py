from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from weekly_intel.collectors.manual import ManualInboxCollector
from weekly_intel.contracts import CollectionWindow, SourceConfig


class ManualInboxTest(unittest.TestCase):
    def test_jsonl_review_article_and_invalid_line(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            inbox = Path(temp_dir) / "inbox.jsonl"
            valid = {
                "url": "https://mp.weixin.qq.com/s/test",
                "title": "KV Cache系统综述",
                "document_type": "review_article",
                "published_at": "2026-07-23T08:00:00+08:00",
                "source_account": "PaperWeekly",
                "summary": "总结KV Cache与推理调度进展。",
            }
            inbox.write_text(
                json.dumps(valid, ensure_ascii=False) + "\n{bad json}\n",
                encoding="utf-8",
            )
            source = SourceConfig(
                source_id="manual_inbox",
                name="Manual",
                source_type="manual",
                connector="ManualInboxCollector",
                tier="Manual",
                options={"inbox_path": str(inbox)},
            )
            batch = ManualInboxCollector().collect(
                source,
                CollectionWindow(
                    datetime(2026, 7, 20, tzinfo=timezone.utc),
                    datetime(2026, 7, 25, tzinfo=timezone.utc),
                ),
            )
            self.assertEqual(batch.status.value, "partial")
            self.assertEqual(len(batch.documents), 1)
            self.assertEqual(
                batch.documents[0].document_type.value, "review_article"
            )
            self.assertEqual(batch.errors[0].code, "invalid_inbox_record")


if __name__ == "__main__":
    unittest.main()
