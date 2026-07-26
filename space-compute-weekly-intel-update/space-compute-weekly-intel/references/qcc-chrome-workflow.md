# 企查查 Chrome 页面上下文融资清单流程

本文件适用于每周境内/境外企查查融资清单的获取、整理与落盘。企查查网页只能通过用户已登录的 Chrome 访问，不使用 Codex 内置浏览器。

## 工具边界（HARD RULE）

允许：

- 用户已经导出的完整 `.xlsx` / `.csv` / `.tsv`；
- 可控制且已登录企查查的用户 Chrome 标签页；
- 从 Chrome 页面触发企查查自身提供的正常导出功能；
- 在已认证页面上下文中复用页面自身融资列表请求，按页取得结构化 JSON；
- 页面接口不可用时，以 UI 逐页读取作为 fallback。

禁止：

- 使用 Codex 内置浏览器（in-app browser）访问、登录或筛选企查查；
- Chrome 不可用时自动退回内置浏览器；
- 读取/复制 cookie、local storage、密码、验证码或浏览器配置来迁移登录态；
- 绕过验证码、频率限制、海外访问提示、付费墙或安全拦截；
- 用 Bocha/WebSearch 结果冒充企查查全量清单。

## 方法优先级

1. 用户已提供的完整文件；
2. 网站自身正常导出；
3. **主方法：Chrome 页面上下文接口 → Raw CSV → 21 列标准化 CSV**；
4. **Fallback：UI 逐页翻页并读取表格**。

接口主方法和 UI fallback 使用相同登录账号、日期窗口和页面筛选条件。不得把关键词搜索、首屏摘录或不完整分页标记为全量。

## 页面上下文接口主流程

1. 先运行 `scripts/check_inputs.py <本周文件夹>`。若境内与境外文件已齐全，直接使用文件，不打开企查查网页。
2. 文件缺失且用户要求网页补齐时，检查是否存在可控制的 Chrome 浏览器能力；只选择 Chrome，不选择 Codex 内置浏览器。
3. 复用用户已经登录的企查查 Chrome 标签页。若未登录，明确请用户在 Chrome 完成登录并回复“登录好了”；不要代输密码或迁移其他浏览器会话。
4. 分别打开境内融资与境外融资页面，用 UI 把日期筛选为本周闭区间 `[start_date, end_date]`，并确认页面自身查询能正常返回。
5. 在 Chrome DevTools Network 中定位页面触发的融资列表 XHR/fetch，记录相对路径、方法、请求体字段、分页字段和响应列表路径。不得凭历史记忆硬编码接口契约；页面升级后必须重新捕获。
6. 在同一企查查页面的 JavaScript 上下文中，以相对路径发送与页面相同形态的请求。只递增 `pageIndex`，保持日期、筛选、排序和 `pageSize` 与已验证请求一致；每页请求间至少等待约 `500ms`。
7. 每页记录 HTTP 状态、页码、返回行数和记录 ID。出现非 2xx、验证码、操作频繁、响应结构变化或持续 pending 时立即停止，不并发轰炸，不自动改 header、签名或频率尝试绕过限制。
8. 将全部接口字段先保存为 `<本周文件夹>/input/qcc_raw/境内融资清单_YYYY-Wxx_接口原始.csv` 或对应境外文件。Raw 文件不得删列、改金额或提前做行业筛选。
9. 运行确定性转换器生成正式 21 列清单：

```bash
scripts/convert_qcc_raw_financing.py \
  <raw.csv> \
  --out <本周文件夹>/input/境内融资清单_YYYY-Wxx_标准化.csv \
  --market domestic \
  --start-date YYYY-MM-DD \
  --end-date YYYY-MM-DD \
  --usd-cny-rate <本次采用的USD/CNY汇率> \
  --fx-date YYYY-MM-DD \
  --fx-source <可追溯来源>
```

10. 标准化列固定为 21 列：原 14 个业务字段 `融资日期 / 项目名称 / 业务描述 / 融资轮次 / 融资金额 / 投资方 / 行业门类 / 行业大类 / 所属城市 / 企业名称 / 成立日期 / 估值 / 来源标题 / 来源链接`，再追加 `amount_original / currency_original / amount_rmb / amount_usd / fx_rate_usd_cny / fx_rate_date / fx_source`。
11. `融资金额`与 `amount_original`均保留接口原文；前者兼容中文标准表，后者供程序统一读取。明确写出的 USD/CNY 币种优先；没有币种时由 `--market domestic` 默认 CNY、`--market overseas` 默认 USD。可确定数值时把基础货币单位的纯数值写入 `amount_rmb`、`amount_usd`；`数千万`等模糊金额保留原文和默认/明确币种，但两个数值列留空；未披露金额不填币种、不换算。
12. 境内融资排序、金额门槛与规模分析使用 `amount_rmb`；境外使用 `amount_usd`。不得用换算结果覆盖 `amount_original`。
13. 再次运行 `check_inputs.py`；两侧文件被识别后，按 `reporting-playbook.md` 的全行业融资筛选规则生成审计表并导入事件池。

## UI 逐页 fallback

只有页面自身查询正常、但页面上下文接口调用无法稳定取得结构化结果时，才退回 UI 逐页读取：

1. 每次点击下一页后至少等待约 `500ms`；
2. 确认页码或首行已经变化后再解析；
3. 记录页面显示总数、已读取页码、各页行数和抓取时间；
4. 保留表格原始金额文本；落盘后仍运行同一转换器生成金额审计列；
5. 未覆盖全部分页不得标记“全量”。

逐页读取使用以下节奏（示意）：

```js
await sky.click({ app: "com.google.Chrome", element_index: nextPageId });
await new Promise(resolve => setTimeout(resolve, 500));
const state = await sky.get_app_state({ app: "com.google.Chrome", disableDiff: true });
// 只有页码或首行已变化时才解析；否则继续等待页面稳定，不重复点击。
```

## 阻断处理

- **Chrome 能力不可用**：停止，要求用户在可控 Chrome 中打开企查查，或直接导出两份文件。
- **未登录**：要求用户在 Chrome 登录后回复；保持该 Chrome 标签页为 handoff，不切换浏览器。
- **验证码/操作频繁**：立即停止并让用户处理；用户明确完成后再继续。不得自动解验证码或提高请求频率。
- **海外访问/地区限制**：报告实际重定向或提示，要求用户在 Chrome 中处理；不得通过内置浏览器、代理或其他站点绕过。
- **只拿到首屏或部分分页**：保存为 `qcc_raw/` 工作底稿并标 `partial`，不得转换成正式全量融资清单，也不得据此生成完整融资模块。

## 完整性自检

- 境内、境外两侧日期窗口一致；
- 原始文件行数与页面显示总数一致，或有明确的导出范围说明；
- 页面总数、导出行数、筛入行数分开记录；
- 首屏摘录、关键词检索结果和人工候选不等于全量清单；
- 每次翻页后等待约 `500ms`，并以页码或首行变化确认新页已加载；不得把重复页计入全量；
- Raw 中的融资金额保持来源原文；标准化清单必须同时存在原值、币种、RMB/USD数值及可追溯汇率元数据；
- Raw 记录 ID 非空且唯一；页数、各页行数之和、Raw 行数与页面总数一致；
- 重要融资仍须回到公司、投资方、交易所或权威媒体做 Pass C 交叉验证。
