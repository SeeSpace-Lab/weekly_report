# 采集源恢复与人工验证

周报运行会把需要人工处理的来源标记为 `needs_attention`，并在命令输出及
`runs/*.json` 的 `human_actions` 中给出入口。处理完成后重新运行同一周次即可。

## WeRSS / 微信公众号

1. 打开本机 `http://127.0.0.1:8001/`，登录 WeRSS。
2. 微信会话失效时，在 WeRSS 中完成二维码扫码。
3. 在 WeRSS 的 Access Keys 页面创建仅供周报使用的访问密钥。
4. 在运行周报的本机环境中设置：

   ```powershell
   $env:WERSS_ACCESS_KEY = "WK..."
   $env:WERSS_SECRET_KEY = "SK..."
   $env:WERSS_API_BASE_URL = "http://127.0.0.1:8001/api/v1/wx"
   $env:WECHAT_FEED_BASE_URL = "http://127.0.0.1:8001/feed"
   ```

采集器会先读取 Feed；如果最新文章超过72小时，会调用 WeRSS 刷新接口，等待后
再次读取。Feed 仍然过期时会停止静默成功，改为提示扫码或验证。访问密钥和微信
凭证不会写入数据库、审计文件或 Git 仓库。

## OpenReview

OpenReview 某个会议触发验证时不会再中断其他会议。若所有会议都触发验证，打开
`human_actions` 提供的地址完成验证或登录，并在自动任务环境中设置合法的
`OPENREVIEW_TOKEN`。系统不会绕过 Cloudflare/Turnstile 验证。

## arXiv 与 Crossref

- arXiv 主 Atom API 对当前出口 IP 限流时，会自动转到官方 OAI-PMH 接口；瞬时
  429、5xx、DNS 和超时会按退避策略处理。
- Crossref 使用精确到秒的 UTC 索引时间窗口，避免同一天但晚于周报截止时刻的
  记录占满首批结果；请求按查询隔离并对瞬时网络错误重试。
- 顶会页面逐页隔离，单个站点的 TLS/403 不会阻断其他官方来源。
