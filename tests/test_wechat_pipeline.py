from __future__ import annotations

import unittest
from datetime import datetime, timezone

from weekly_intel.collectors.wechat import WechatPoolCollector
from weekly_intel.contracts import CollectionWindow, SourceConfig


RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:content="http://purl.org/rss/1.0/modules/content/">
  <channel>
    <title>PaperWeekly</title>
    <item>
      <guid>wechat-article-1</guid>
      <title>KV Cache与推理调度论文解读</title>
      <link>https://mp.weixin.qq.com/s/example</link>
      <pubDate>Thu, 23 Jul 2026 08:00:00 +0800</pubDate>
      <description><![CDATA[近期KV Cache研究综述。]]></description>
      <content:encoded><![CDATA[
        <p>详细讨论动态功耗预算与推理调度。</p>
        <a href="https://arxiv.org/abs/2607.12345v2">论文</a>
      ]]></content:encoded>
    </item>
  </channel>
</rss>
""".encode()


class WechatPipelineTest(unittest.TestCase):
    def setUp(self) -> None:
        self.window = CollectionWindow(
            datetime(2026, 7, 20, tzinfo=timezone.utc),
            datetime(2026, 7, 25, tzinfo=timezone.utc),
        )

    def test_rss_article_and_arxiv_link(self) -> None:
        source = SourceConfig(
            source_id="wechat_paperweekly",
            name="PaperWeekly",
            source_type="wechat",
            connector="WechatPoolCollector",
            tier="S_Core",
            options={
                "feed_url": "https://feeds.example/paperweekly.xml",
                "account_id": "paperweekly",
            },
        )
        collector = WechatPoolCollector(
            fetcher=lambda url, headers, timeout: RSS
        )
        batch = collector.collect(source, self.window)
        self.assertEqual(batch.status.value, "ok")
        self.assertEqual(len(batch.documents), 1)
        document = batch.documents[0]
        self.assertEqual(document.document_type.value, "review_article")
        self.assertEqual(
            document.metadata["related_arxiv_ids"], ["2607.12345"]
        )
        self.assertIn("动态功耗预算", document.content_text)

    def test_missing_subscription_is_blocked(self) -> None:
        source = SourceConfig(
            source_id="wechat_paperweekly",
            name="PaperWeekly",
            source_type="wechat",
            connector="WechatPoolCollector",
            tier="S_Core",
        )
        batch = WechatPoolCollector().collect(source, self.window)
        self.assertEqual(batch.status.value, "blocked")
        self.assertEqual(
            batch.errors[0].code, "subscription_not_configured"
        )


if __name__ == "__main__":
    unittest.main()
