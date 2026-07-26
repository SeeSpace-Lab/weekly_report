from __future__ import annotations

import unittest
import os
import urllib.error
from datetime import datetime, timezone
from unittest.mock import patch

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

EMPTY_RSS = b'<?xml version="1.0"?><rss><channel></channel></rss>'


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

    def test_empty_feed_is_not_reported_as_no_update(self) -> None:
        source = SourceConfig(
            source_id="wechat_empty",
            name="Empty",
            source_type="wechat",
            connector="WechatPoolCollector",
            tier="S_Core",
            options={"feed_url": "https://feeds.example/empty.xml"},
        )
        batch = WechatPoolCollector(
            fetcher=lambda url, headers, timeout: EMPTY_RSS
        ).collect(source, self.window)
        self.assertEqual(batch.status.value, "partial")
        self.assertEqual(batch.stats["health_status"], "empty_feed")
        self.assertEqual(batch.errors[0].code, "empty_feed")

    def test_authorization_header_uses_environment_secret(self) -> None:
        captured = {}

        def fetcher(url, headers, timeout):
            captured.update(headers)
            return RSS

        source = SourceConfig(
            source_id="wechat_auth",
            name="Auth",
            source_type="wechat",
            connector="WechatPoolCollector",
            tier="S_Core",
            options={
                "feed_url": "https://feeds.example/auth.xml",
                "auth_token_env": "TEST_WECHAT_TOKEN",
            },
        )
        with patch.dict(os.environ, {"TEST_WECHAT_TOKEN": "secret-value"}):
            batch = WechatPoolCollector(fetcher=fetcher).collect(
                source, self.window
            )
        self.assertEqual(batch.status.value, "ok")
        self.assertEqual(captured["Authorization"], "Bearer secret-value")
        self.assertNotIn("secret-value", str(batch))

    def test_http_and_network_errors_are_classified(self) -> None:
        source = SourceConfig(
            source_id="wechat_error",
            name="Error",
            source_type="wechat",
            connector="WechatPoolCollector",
            tier="S_Core",
            options={"feed_url": "https://feeds.example/error.xml"},
        )

        def unauthorized(url, headers, timeout):
            raise urllib.error.HTTPError(url, 401, "Unauthorized", {}, None)

        auth_batch = WechatPoolCollector(fetcher=unauthorized).collect(
            source, self.window
        )
        self.assertEqual(auth_batch.status.value, "blocked")
        self.assertEqual(auth_batch.errors[0].code, "feed_auth_failed")
        self.assertFalse(auth_batch.errors[0].retryable)

        def network_error(url, headers, timeout):
            raise urllib.error.URLError("temporary DNS failure")

        network_batch = WechatPoolCollector(fetcher=network_error).collect(
            source, self.window
        )
        self.assertEqual(network_batch.status.value, "error")
        self.assertEqual(network_batch.errors[0].code, "feed_network_error")


if __name__ == "__main__":
    unittest.main()
