# 搜索扇出 Playbook（Search Fan-out）

当进入阶段 1（生成本周扫描计划）和阶段 2（建立事件池）时使用本文件。

## 为什么需要强制扇出

LLM 内置 web search 不会主动跑爬虫，只在被显式要求时执行查询；且查询会被自动归一化重写（query rewriting），把"商业航天 + 太空算力 + AI"这类交叉查询折叠成更通用的词，导致长尾事件丢失。

太空算力位于"商业航天 × AI 算力 × 芯片 × 政策"四个垂直的交集。**单一查询词无法覆盖完整事件池。** 必须显式列出多条查询，按"垂直 × 时间 × 玩家 × 邻接"四维度并行扇出。

核心原则：**覆盖优先，后置过滤（coverage over filtering）**。先把可能相关的事件全部捞回事件库，由阶段 3-4 的去重、评分、同心圆判断负责筛选；不要在搜索阶段就做相关性筛选。

## 工具调度（WebSearch + WebFetch 三遍工作流）

WebSearch 和 WebFetch 能力不同，必须配合使用，单用任何一个都会漏：

| 工具 | 擅长 | 不擅长 |
|---|---|---|
| **WebSearch** | 用关键词宽召回，发现未知 URL（英文/美区来源强） | 只返回搜索结果摘要；非新闻型来源（GovInfo 法案原文、SEC EDGAR S-1 索引、FERC News、地方政府栏目）几乎召不回；**且为 US-only，中文政策/地方政府/企查查类融资/国内行业来源系统性召不回**（见下文「双轨检索」） |
| **WebFetch** | 抓取已知 URL 的完整内容，能读栏目主页和原文 | 不能发现未知 URL；必须先有具体地址 |

## 双轨检索（国内轨 / 海外轨）— 进入 Pass A 前必读

WebSearch 是 **US-only** 检索：英文/美区来源召回强，但中文政策、地方政府栏目、企查查类融资、国内行业号召**系统性召不回**。因此搜索必须分两轨执行：

| 轨 | 覆盖对象 | 工具 |
|---|---|---|
| **海外轨** | 美国/欧洲/国际：发射、SEC、FCC、FERC、SpaceNews/Payload、公司 IR 等英文来源 | WebSearch + WebFetch（维持原三 Pass） |
| **国内轨** | 中国政策/科技/融资、部委与地方政府栏目、中文行业媒体 | **Bocha 博查 MCP**：`bocha_web_search`（语义增强时用 `bocha_ai_search`）；融资/工商的企查查网页仅通过用户已登录的 Chrome 或用户导出文件处理，禁止使用 Codex 内置浏览器 |

**国内轨（Bocha）工具用法：**

- `bocha_web_search(query, freshness, count)`：`freshness` 传本周窗口区间 `YYYY-MM-DD..YYYY-MM-DD`（如 `2026-05-25..2026-05-31`），`count` 取 10–50。返回 `name/url/summary/siteName/datePublished`，直接并入候选清单。
- Bocha 结果自带正文摘要，能**绕开 gov.cn 证书错误 / 404**：Pass B 中被反爬挡掉的中国部委/地方政府栏目（MIIT 信通司、国防科工局、发改委解读平台、地方科技局），改用 `bocha_web_search` 以"机构名/政策关键词 + 本周 freshness"召回，替代 WebFetch 直抓。

**分流规则：**

- 维度 1 的「中国政策 / 中国科技 / 中国融资」、维度 2 的中国玩家、维度 4 的中国交易所/部委入口 → **国内轨（Bocha）**。
- 维度 1 的「美国政策 / 美国科技 / 美国融资」、维度 2 的美国玩家、维度 4 的 GovInfo/Congress/SEC/FCC/FERC/FAA → **海外轨（WebSearch）**。
- `pass_a_query_count` = 两轨查询数之和；两轨各自计入对应维度下限。Bocha 查询与 WebSearch 查询**同等计为 Pass A 查询**。

**前置检查（MUST）：** 进入阶段 1 前，`scripts/check_inputs.py` 输出 `cn_search_mcp.installed`。若为 `false`，**必须先停下来提示用户安装 Bocha MCP**（安装段见下），并说明"未安装将导致中国政策/融资召回不全、CN 政策轴覆盖不足"。用户可选择仍然继续（fail-soft），但要在周报第四章「密度说明」里标注"国内轨 MCP 缺失，CN 覆盖依赖 WebSearch + 手工补料"。

**Fail-soft（Bocha 不可用时）：** ① 退回 WebSearch 中文 query（召回弱，已知缺口）；② 请用户用本地网络补料（贴政策链接 / `! curl` 拉 gov 原文）；③ 交付里显式标注 CN 覆盖受限。**不得因 Bocha 缺失就降低事件池 / 正文 / 各板块阈值**——阈值不变，只如实标注覆盖来源。

**Bocha 安装（官方 uv 版，已验证可用）：**

```bash
git clone https://github.com/BochaAI/bocha-search-mcp.git ~/bocha-search-mcp
claude mcp add-json bocha '{"command":"uv","args":["--directory","/Users/<你的用户名>/bocha-search-mcp","run","bocha-search-mcp"],"env":{"BOCHA_API_KEY":"<YOUR_BOCHA_API_KEY>"}}' --scope user
```

API key 在 https://open.bochaai.com 领取（按量付费，用户自备）。**勿用** npx 包 `@humansean/mcp-bocha`（Node 新版下启动即崩："Server does not support completions"）。装/改后需**重开 Claude Code** 才能加载该 MCP。

---

每次完整版周报，搜索阶段必须依次跑三个 Pass：

### Pass A — WebSearch 发现层（覆盖宽）

执行本文件维度 1-4 的 25+ 条结构化查询；命中的 URL 收集到候选清单。

- **按「双轨检索」分流（见上文）**：中文 query（中国政策/科技/融资/玩家/部委入口）走国内轨 `bocha_web_search`（带本周 `freshness=YYYY-MM-DD..YYYY-MM-DD`）；英文 query 走 WebSearch。两轨命中合并进同一候选清单，`pass_a_query_count` 合并计数。Bocha 未安装时按「双轨检索」段的 fail-soft 处理并提示用户。
- 每条查询单独调用一次 WebSearch（或 Bocha），不要把多条合并成一句宽查询。
- 命中后**先不入事件库**，只记录 URL、标题、查询词、初步分类（板块/国家）。
- 维度 4（GovInfo/FERC/SEC/FAA/CNInfo/SSE/SZSE/HKEXnews）建议用 `site:` 限定增强召回精度，但召回率仍有限——这正是为什么需要 Pass B。

### Pass B — WebFetch 主动扫描层（深度强，HARD MANDATORY）

Pass B 用 WebFetch 主动抓取一组已知高价值栏目页，覆盖 Pass A 召不回的非新闻型来源。**必须同时覆盖本文件策展清单和 `source_map.csv` 中所有有效的 `tier = S_Core` URL。**

#### Single Source of Truth：Pass B 必扫集合 = 策展清单 ∪ source_map S_Core

**Pass B 全量基准 N 由脚本生成的并集清单定义，不是任何文档中写死的具体数字。** 当前必扫集合为：本节下方"强制扫描的栏目主页策展清单" + `source_map.csv` 中 `tier = S_Core` 且 `url` 为 `http/https` 的来源，按规范化 URL 去重。

进入 Pass B 前必须优先运行：

```bash
scripts/build_pass_b_required.py
```

该脚本输出 `pass_b_total_required` 和 `pass_b_required_urls`。`pass_b_required_urls` 是对象数组；执行 WebFetch 时必须逐条取 `pass_b_required_urls[*].url`。agent 必须：

1. 使用脚本输出的 `pass_b_required_urls[*].url` 作为 Pass B 实际 WebFetch URL 清单，保留对象中的 `normalized_url` / `required_by` / `source_id` / `source_ids` 作为合规记录字段；
2. 在 Pass B 完成度 JSON 中填 `pass_b_total_required`，数值必须等于脚本输出；
3. 所有规则文本中的 "Pass B 全量"、"Pass B 完成"等表述指的都是 `pass_b_attempted == pass_b_total_required`；
4. 若脚本不可运行，才允许手工合并本节策展清单与 `source_map.csv` 的全部有效 `S_Core` URL，并在阶段日志说明手工计数方式。

`source_map.csv` 中 `tier = S_Core` 是每周必扫硬约束；本节策展清单用于补足更具体的栏目页、政府/监管专用入口和历史漏召回高风险来源。两者任一出现的有效 URL 都必须进入 Pass B 必扫集合。

**HARD RULE — Pass B 全量扫描，不可跳过、不可裁剪：**

- `scripts/build_pass_b_required.py` 输出的全部 `pass_b_required_urls[*].url` **必须逐条 WebFetch**，每条返回 `ok` / `blocked` / `empty` 三种状态之一并记录到 Pass B 完成度 JSON（见本节末尾）。
- 不存在"时间预算紧 / 用户没要求那么多 / 用户先要个简版"等任何合法跳过 Pass B 的路径。Pass A（WebSearch）对官方/监管/交易所/IR 类来源召回率极低，跳过 Pass B = 系统性放弃一手公告。
- 如果某条 URL `blocked` 或 `empty`，必须尝试 RSS / 备用页 / `site:` 替代查询，三种替代都失败才允许标记为 `blocked` 关闭，不允许直接跳过。
- Pass B 完成数 < `pass_b_total_required` 视为覆盖不足，按"搜索合规门 Fail-Closed"输出"搜索未达标报告"停止生成。**唯一允许的后续动作是回阶段 1-2 补扫直到 `pass_b_attempted == pass_b_total_required`；不存在"用户授权降级"路径**（参本文件 Fail-Closed 段与 SKILL.md 阶段 1 契约层 HARD RULE 第 3 条）。
- 严禁的兜底路径：① 自评"时间紧"减少扫描条数；② 只扫前 N 个声称"覆盖核心来源"；③ 把 Pass A 命中数高作为"Pass B 可省略"的理由；④ **只扫本节策展清单但漏掉 `source_map.csv` 中的有效 S_Core URL**；⑤ 声称"已扫 35 / 已扫 N 条"但 N < 脚本输出的 `pass_b_total_required`。

强制扫描的栏目主页策展清单（**与 source_map S_Core 并集后全量必扫**）：

中国政策与官方：
- `https://www.cnsa.gov.cn/n6758823/n6758838/index.html`（CNSA 新闻）
- `https://www.miit.gov.cn/jgsj/xxhfzs/`（工信部信通司）
- `https://www.ndrc.gov.cn/xxgk/jd/jd/`（发改委政策解读）
- `https://www.gov.cn/zhengce/zuixin.htm`（中国政府网最新政策）
- `http://www.sastind.gov.cn/`（国防科工局）

中国交易所与上市公司：
- `http://www.cninfo.com.cn/new/disclosure/stock`（巨潮资讯）
- `http://www.sse.com.cn/disclosure/`（上交所）
- `https://www.szse.cn/disclosure/`（深交所）
- `https://www.hkexnews.hk/`（港交所披露）

美国政府与立法：
- `https://www.govinfo.gov/app/collection/bills`（GovInfo 法案）
- `https://www.congress.gov/search?q=&searchResultViewType=expanded`（Congress.gov 法案搜索）
- `https://www.federalregister.gov/`（Federal Register）
- `https://www.ferc.gov/news-events/news`（FERC 新闻）
- `https://www.faa.gov/space/news_updates`（FAA AST）
- `https://www.fcc.gov/news-events`（FCC 新闻）

美国国防与航天：
- `https://www.ssc.spaceforce.mil/Newsroom`（SSC 新闻）
- `https://www.sda.mil/news/`（SDA 新闻）
- `https://www.darpa.mil/news`（DARPA 新闻）
- `https://www.nasa.gov/news/`（NASA 新闻中心）
- `https://www.nasa.gov/commercial-crew/`（NASA Commercial Crew 任务页）
- `https://www.nasa.gov/commercial-resupply/`（NASA Commercial Resupply / CRS 货运任务页，含 Cygnus / Dragon 任务时间线）
- `https://www.nasa.gov/iss/`（ISS 主页 / 科研载荷）
- `https://www.nro.gov/news-media-featured-stories/`（NRO 新闻）

美国商业空间站与发射运营商（必须扫，2026 年商业空间站节奏快）：
- `https://www.vastspace.com/news`（Vast Space，含 Large Docking Adapter / Cedars-Sinai 等里程碑）
- `https://www.axiomspace.com/newsroom`（Axiom Space）
- `https://www.sierraspace.com/news/`（Sierra Space / Dream Chaser）
- `https://www.blueorigin.com/news`（Blue Origin，含 New Glenn 静态点火/试飞、Orbital Reef）
- `https://www.spacex.com/launches/`（SpaceX Launches，覆盖 Falcon 助推器复用里程碑）
- `https://www.rocketlabusa.com/updates/`（Rocket Lab 更新）
- `https://www.amazon.com/about-amazon/news`（Amazon About 新闻中心，覆盖 Kuiper / Globalstar 类大型并购）
- `https://www.globalstar.com/en-us/about/news`（Globalstar 新闻中心）

美国融资与公告：
- `https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&type=S-1&dateb=&owner=include&count=40`（SEC EDGAR S-1）
- `https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&type=8-K&dateb=&owner=include&count=40`（SEC EDGAR 8-K，并购/重大事项）
- `https://www.prnewswire.com/news-releases/news-releases-list/?category=23300`（PR Newswire 太空板块）
- `https://www.globenewswire.com/`（GlobeNewswire）
- `https://www.businesswire.com/portal/site/home/`（Business Wire）

中国 AI 算力 / 智算政策栏目（外圈，默认入事件库；入正文由阶段 4 按 reporting-playbook.md "外圈两层规则" 判定）：
- `https://www.digitalpolicyoffice.gov.hk/en/our_work/`（香港数字政策办公室，含 WIC / AI Supercomputing）
- `http://gxj.gz.gov.cn/`（广州工信局，含大模型与算力补贴政策）
- `https://kjj.zhengzhou.gov.cn/`（郑州科技局，含 6 万卡科学智能计算集群）
- `https://sheitc.sh.gov.cn/`（上海经信委，含商业航天产融对接、AI 算力调度）
- `https://www.ndrc.gov.cn/xxgk/jdpt/`（发改委解读平台，含民间投资表述）

美国 AI 政策与执法（外圈，默认入事件库；入正文由阶段 4 按 reporting-playbook.md "外圈两层规则" 判定）：
- `https://www.whitehouse.gov/briefing-room/`（白宫简报，含 AI 公司会谈、行政令）
- `https://www.bis.doc.gov/index.php/about-bis/newsroom/press-releases`（BIS 新闻发布，含 AI 芯片走私执法）
- `https://oversight.house.gov/release/`（众议院监督委员会发布，含 AI 芯片走私听证）
- `https://www.anthropic.com/news`（Anthropic 新闻，含政府关系节点）

行业垂直媒体：
- `https://spacenews.com/`
- `https://spaceflightnow.com/`
- `https://payloadspace.com/`
- `https://breakingdefense.com/full-coverage/space/`（Breaking Defense Space）
- `https://arstechnica.com/space/`（Ars Technica Space）

WebFetch 用法：

- 每个栏目主页用一次 WebFetch，prompt 里告诉它"提取本周时间窗口 `[start, end]` 内的标题、链接、日期"。
- 命中后把候选 URL/标题加入候选清单，与 Pass A 的命中合并去重。
- **脚本输出的并集清单全部条目必须扫，无任何"降到核心 N 个"的合法路径，不存在"模式"概念。** 输出形态（老板版 / 老板版HTML / 完整版 / 数据库版）只决定写多少、怎么排版，不影响搜索覆盖。
- 高密度周（如 W16 类含商业空间站节点 + 大型并购 + 立法节点 + 多笔大额融资）：把 `tier = A_Active` 来源的栏目主页也加入扫描（约 50-80 个），以匹配 W16 手工版 78 条正文规模。

#### Pass B 完成度 JSON（必须在进入 Pass C 前输出给用户）

Pass B 全部扫完后，进入 Pass C 之前必须以 JSON 块输出完成度自报。**`pass_b_total_required` 必须来自 `scripts/build_pass_b_required.py` 输出的并集清单，不得只数本节策展清单，也不得使用记忆中的旧数字**：

```json
{
  "pass_b_total_required": <脚本输出的并集清单条数>,
  "pass_b_attempted": <实际 WebFetch 调用过的 URL 数，必须 == pass_b_total_required>,
  "pass_b_required_source_summary": {
    "curated_pass_b_url_count": <本文件策展清单 URL 数>,
    "source_map_s_core_url_count": <source_map 中有效 S_Core URL 数>,
    "source_map_s_core_skipped_count": <source_map 中无有效 http/https URL 的 S_Core 数>
  },
  "pass_b_status": {
    "ok": <成功抓到内容的 URL 数>,
    "blocked": <反爬/重定向/403 的 URL 数，且已尝试 RSS/备用页失败>,
    "empty": <抓到内容但本周时间窗口内 0 命中的 URL 数>
  },
  "pass_b_urls": [
    {"url": "https://www.cnsa.gov.cn/...", "status": "ok", "hits": 3},
    {"url": "https://www.govinfo.gov/...", "status": "blocked", "fallback_tried": ["RSS", "site:"], "fallback_result": "still_blocked"},
    ...（脚本输出的全部 URL 逐一列出，缺一不可）
  ],
  "pass_b_complete": true
}
```

**判定规则**：
- `pass_b_total_required` ≠ `scripts/build_pass_b_required.py` 输出的 `pass_b_total_required` → 计数错误，必须重新生成；
- `pass_b_attempted` < `pass_b_total_required` → Pass B 未完成，必须回去补扫；
- `pass_b_urls` 数组长度 ≠ `pass_b_total_required` → 明细缺失，必须补全；
- 缺任何一条 URL 的状态记录 → 视为该 URL 未扫，必须回去补扫；
- 任一有效 `source_map.csv` `S_Core` URL 未出现在 `pass_b_urls` → 视为 S_Core 漏扫，必须补全；
- 不允许进入 Pass C。

这个 JSON 是 Pass B 的合规证据，缺了它就是合规未达标。

### Pass C — WebFetch 验证层（精度高）

对 Pass A + Pass B 合并去重后的候选 URL，逐个用 WebFetch 抓原文：

- 提取确切日期、金额、机构、标题、关键事实，写入事件库。
- 检验事件 `date` 是否落在本周时间窗口闭区间内；不在的剔除（除非用户已确认延迟披露规则）。
- 标记主来源 + secondary_sources。
- 记录 `source_tier`（参考 source_map.csv）。

### 三 Pass 命中合并规则

- 同一事件被 Pass A 和 Pass B 都命中：保留 Pass B 来源（通常是官方/交易所/Newswire），Pass A 命中作为发现路径记录。
- 同一事件 Pass C 验证时发现 URL 失效或内容与摘要不符：标记 `analyst_note`，找补充来源后再入库。
- Pass A/B 没命中但用户/手工融资清单已提供的事件：直接进入 Pass C 验证。

#### 手工融资来源补全门（HARD MANDATORY）

企查查、工商变更或用户导入清单只承担“发现与交叉验证”角色，不得因为导入时 `source_url = N/A` 就直接断言“没有公开来源”。以下融资在阶段 4 评级和老板版选卡之前必须逐笔补做公开来源检索：① 所有预评 S/A；② 所有拟 `include_in_report = Yes/Brief`；③ 境内原币 ≥ 1 亿元或境外原币 ≥ 1,000 万美元；④ 金额未达门槛但直接涉及太空算力、太空数据、星载 AI、卫星激光通信或宇航级芯片。

每笔至少执行并记录三类查询：`"公司全称" + 金额/轮次`、`"公司简称" + 融资 + 本周日期`、`公司 + 投资方/领投方`；国内轨使用 Bocha 并检查公司公众号/官网、投资方公告、政府园区、主流财经媒体，境外轨检查公司 newsroom、Business Wire / PR Newswire / GlobeNewswire、投资方公告、SEC/交易所及 Reuters 等。找到可解析公开页后，必须用其更新事件库 `source_url/source_name/source_type/source_tier`，企查查降为 `secondary_sources` 或发现标记。只有上述查询全部无有效结果且在 `analyst_note` 留下查询与失败原因后，才允许标“公开来源未找到”；禁止把“未搜索”写成“无公开来源”。

### 失败模式

如果 `pass_a_query_count < 25` / `pass_a_hit_count < 30` / **Pass B `pass_b_attempted < pass_b_total_required`（即未全量扫完）** / 合并去重后候选 URL 低于 80 条 / 事件表入库 < 80 条 / 完整版正文 < 70 条，任一不达标即视为覆盖不足（W16 仅作容量参照：78 条事件量级、100+ 事件表底量；W16 的 41 融资是反例，不得复刻）。检查：

- WebSearch 是否被自动归并；逐条复查实际查询字符串。
- WebFetch 抓栏目主页时是否被反爬阻挡或重定向；改抓 RSS 或备用页面。
- 是否漏跑维度 4 专用入口；强制补做。
- 是否在阶段 2 把 Pass A/B 命中的事件错误过滤；阶段 2 不允许相关性筛选，参 SKILL.md 阶段 2"全员入库"硬规定。
- 融资模块 Database_Only 比例是否 > 30%；过度降级会把 5C.1 行数压到下限以下。

### Fail-Closed 搜索合规门（HARD RULE）

以上检查全部走完且补扫后仍不达标时，**不允许降级生成正式完整版周报**，必须停下来输出一份"搜索未达标报告"，**禁止把它包装成完整版交付**。报告必须包含以下五项证据：

1. **已执行的 Pass A 查询词数量与完整清单**（含每条查询字符串、命中数、是否归并/限流/失败原因）；
2. **Pass B 完成度 JSON**（schema 见上文 Pass B 段末尾，含 `pass_b_required_source_summary`、`pass_b_total_required` / `pass_b_attempted` / `ok` / `blocked` / `empty` 三态计数 + 策展清单 ∪ S_Core 全量 URL 明细 + 每条 `blocked` 的替代尝试记录）；
3. **Pass C 验证成功的事件数**（含 S/A/B/C 分布、时间窗口外被剔除数、字段缺失被打回数）；
4. **低于阈值的具体项**（参上方"覆盖不足"六档：`pass_a_query_count < 25` / `pass_a_hit_count < 30` / Pass B `pass_b_attempted < pass_b_total_required` / 候选 < 80 / 事件池 < 80 / 正文 < 70）；
5. **下一轮必须补扫的清单**：`source_map.csv` 中待补的 `tier=S_Core` 与 `A_Active` 来源（按 `source_id` 列出）、未触达的强制扇出维度（维度 1–4）、必须新增的关键词或玩家锚点。

输出"搜索未达标报告"后**停止生成**，等待用户回应。允许的后续路径只有两条：

- **回阶段 1-2 补扫**（首选）：按报告第 5 项执行补扫，覆盖达标后再进入阶段 3-5 生成正式完整版。
- **不存在降级路径**：搜索覆盖未达标时唯一允许的后续动作是回阶段 1-2 补扫。**禁止**用"用户接受不完整草稿"、"用户只要老板版"等任何措辞作为放宽下限的兜底——这些回复只能影响输出形态（写哪些、不写哪些），不能影响搜索覆盖与合规阈值。

**严禁的兜底路径**（视为严重违规）：

- 在覆盖未达标时直接生成完整版正式稿；
- 用"事件密度低"作为不补扫的理由；
- 编造、跨窗口挪用、把未验证转载写成事实、硬升 B/C 来掩盖覆盖不足；
- 把"搜索未达标报告"伪装成完整版正文的"四、主线总结"段；
- 自我判定"时间紧"就跳过 Pass B 或只扫前 N 个 URL（参上文 Pass B HARD MANDATORY 段）。

## 强制扇出要求（MANDATORY）

Pass A 有**两个独立下限**，分别对应"行为下限"（agent 真的发了多少次 WebSearch）和"产出下限"（这些 WebSearch 一共召回了多少条独立 URL）。两者不可互相替代，schema 中作为**两个独立字段**存在：

| 字段 | 含义 | 下限 |
|---|---|---|
| `pass_a_query_count` | Pass A 实际调用 WebSearch 的次数（= 唯一查询字符串数）| ≥ 25 |
| `pass_a_hit_count` | 上述 WebSearch 累计召回的去重 URL 总数 | ≥ 30 |

**两个下限都必须满足**——25 次查询但只命中 12 个 URL = 不达标；50 个 URL 但只跑了 18 次查询（被 LLM 自动归并）也 = 不达标。Fail-Closed 段中提到的 "Pass A < 30" 指的是 `pass_a_hit_count < 30`。

每次搜索阶段必须满足以下下限。**所有下限在所有情况下保持原值，不存在"折扣"、"模式降级"、"轻量草稿"等任何放宽路径**——用户的输出形态偏好（老板版 / 老板版HTML / 完整版 / 数据库版）只决定写哪些、怎么排版，不影响搜索覆盖。下限不达标时，唯一允许的后续动作是补扫直到达标，参上文 Fail-Closed 段。

| 维度 | 下限（Pass A 查询条数）|
|---|---|
| 总查询条数（`pass_a_query_count`）| ≥ 25 条 |
| 维度 1：垂直 × 国家 × 时间 | ≥ 8 条（中政/中科/中融/美政/美科/美融，每类至少 1 条；其中政策板块和融资板块至少 2 条） |
| 维度 2：玩家驱动（公司/机构名 × 本周） | ≥ 8 条（覆盖核心玩家清单中至少 8 家） |
| 维度 3：邻接触发（AI 算力、芯片、出口管制、电网/数据中心、D2D 并购等） | ≥ 5 条 |
| 维度 4：立法 / 交易所 / 政府原文专用入口（GovInfo/FERC/SEC/FAA/Federal Register/CNInfo/SSE/SZSE/HKEXnews） | ≥ 4 条 |

不允许把"商业航天周报 本周"这类宽泛查询当作单条覆盖；这只算"维度 1 中的 1 条"。每条查询都要有明确的国家/玩家/触发词锚点。

**Pass A 完成度自报（与 Pass B JSON 同期输出）**：

```json
{
  "pass_a_query_count": <实际调用 WebSearch 的唯一次数>,
  "pass_a_hit_count": <去重后召回 URL 总数>,
  "pass_a_dimension_breakdown": {
    "dim_1_vertical_country_time": <N 条查询>,
    "dim_2_player_driven": <N 条查询>,
    "dim_3_adjacent_trigger": <N 条查询>,
    "dim_4_specialized_portal": <N 条查询>
  },
  "pass_a_complete": <true/false>
}
```

`pass_a_query_count < 25` 或 `pass_a_hit_count < 30` 或任一维度低于本表下限 → Fail-Closed。

## 维度 1：垂直 × 国家 × 时间

把"国家 × 板块 × 时间窗口"展开成网格。`<window>` 替换为 ISO 周窗口，例如 `2026年4月13日 OR 4月14日 OR ... OR 4月19日`，或英文 `April 13 2026..April 19 2026`。

中国政策（至少 2 条）：

- `太空算力 政策 OR 工信部 OR 发改委 <window>`
- `商业航天 安全监管 OR 准入 OR 标准 OR 央地协同 <window>`
- `AI 算力 OR 智算 OR 数据中心 政策 OR 兑现 OR 补贴 OR 集群 <window>`
- `卫星互联网 OR 低轨 政策 OR 频谱 OR 授权 <window>`

中国科技：

- `(力箭 OR 朱雀 OR 长征 OR 谷神星 OR 双曲线 OR 引力一号) 发射 OR 入轨 <window>`
- `星载 AI OR 在轨计算 OR 遥感 AI OR 星上处理 <window>`
- `(吉林一号 OR 高分 OR 千帆 OR 国网 OR GW 星座) 卫星 <window>`
- `可重复使用 火箭 OR 复用 验证 OR 试验 <window>`

中国融资：

- `商业航天 融资 OR 中标 OR 并购 OR 科创债 OR 产业基金 <window>`
- `AI 推理 芯片 融资 OR Pre-A OR 战略投资 <window>`
- `(企查查 OR IT桔子 OR 投资界 OR 36氪) 商业航天 OR 太空 <window>`

美国政策：

- `(MATCH Act OR SCALE Act OR CHIPS) GovInfo <window>`
- `(USSF OR SSC OR SDA OR NRO) award OR contract OR IDIQ <window>`
- `(FERC OR DOE) data center OR large load OR interconnection <window>`
- `(BIS OR Commerce) export controls OR entity list <window>`
- `(FAA OR FCC) commercial space OR launch OR satellite OR D2D <window>`

美国科技：

- `(SpaceX OR Blue Origin OR Rocket Lab OR ULA OR Firefly) launch OR static fire OR mishap <window>`
- `(NASA OR ISS OR JPL) experiment OR cargo OR payload <window>`
- `(Vast OR Axiom OR Sierra Space) commercial space station <window>`
- `(Ubotica OR Ramon.Space OR AMD Space OR Microchip Space) onboard AI OR processor <window>`
- `(Orbital OR Starcloud OR Lonestar) space data center OR LEO compute <window>`
- `(Planet OR Maxar OR BlackSky OR Capella OR ICEYE) imagery OR contract <window>`

美国融资：

- `(PR Newswire OR GlobeNewswire OR Business Wire) space OR satellite OR commercial space funding <window>`
- `(SEC EDGAR) S-1 OR 8-K OR Form D space OR satellite <window>`
- `(Crunchbase OR PitchBook) space tech OR aerospace funding <window>`
- `(Cerebras OR SambaNova OR Groq OR Tenstorrent) IPO OR funding OR S-1 <window>`

跨国/国际（至少 1 条）：

- `(ESA OR JAXA OR ISRO OR UKSA) cooperation OR partnership commercial <window>`

## 维度 2：玩家驱动（公司 × 本周）

每周从下面"核心玩家清单"中至少抽 8 家做单独查询：`"<公司名>" news OR press <window>`。新公司若两周内出现高相关信号，加入清单并在 `信息源地图更新建议` 提议升级 Watch。

清单按价值密度排序，前 12 家几乎每周都应扫一次。

中国侧：

1. CASC / 中国航天科技集团
2. CASIC / 中国航天科工集团
3. 中国星网（China SatNet）
4. 垣信卫星（SpaceSail，G60 千帆）
5. 银河航天（GalaxySpace）
6. 时空道宇（Geespace）
7. 蓝箭航天（LandSpace）
8. 中科宇航（CAS Space）
9. 星河动力（Galactic Energy）
10. 东方空间（Orienspace）
11. 天兵科技（Space Pioneer）
12. 长光卫星（吉林一号）
13. 航天宏图（PIESAT）
14. 中科星图（GEOVIS）
15. 千乘探索 / ADA Space
16. 微纳星空（MinoSpace）
17. 国电高科（Guodian Gaoke）
18. 行云集成电路
19. 元川微 / 芯擎科技 / 朋熙半导体
20. 清博空天 / 百灵航天

美国侧：

1. SpaceX
2. Blue Origin
3. Rocket Lab
4. AST SpaceMobile
5. Amazon Leo / Project Kuiper
6. Globalstar
7. Planet
8. Maxar / Capella / BlackSky / ICEYE / Umbra / HawkEye 360
9. Vast
10. Axiom Space
11. Sierra Space
12. Loft Orbital
13. Muon Space
14. Ubotica
15. Ramon.Space
16. AMD Space / Microchip Space / BAE Systems Space Electronics / Frontgrade / CAES
17. Turion Space / True Anomaly / Starfish Space / Scout Space / LeoLabs / Slingshot Aerospace
18. Anduril Space / Astranis / Intuitive Machines / Quantum Space / Redwire
19. Orbital / Starcloud / Lonestar Data Holdings
20. Cerebras / Groq / SambaNova / Tenstorrent

## 维度 3：邻接触发（不要因为"非主航道"漏掉）

太空算力的关键间接信号常出现在邻接领域。以下触发词即使不命中"星上计算"，也要在事件池里保留至少候选行；后置由同心圆评分决定是否进正文：

- AI 数据中心、AI Supercloud、AI 推理云
- 数据中心电网接入、large load interconnection
- AI 出口管制 / 算力总量 / cloud access controls
- CPO / 光互连 / silicon photonics
- 抗辐照 / radiation-hardened / space-grade
- 国产 GPU / GPGPU / FPGA / AI ASIC
- D2D / Direct-to-Cell / Direct-to-Device 并购与频谱
- 量子加速 AI、AI 服务器
- 卫星地面站 / 数据下行 / 星间激光链路

## 维度 4：政府/交易所/立法专用入口

这些来源不会被通用搜索召回，必须显式查询：

| 入口 | 用途 | 推荐查询 |
|---|---|---|
| GovInfo (govinfo.gov) | 美国国会法案原文 | `site:govinfo.gov MATCH OR SCALE OR CHIPS OR space <window>` |
| Congress.gov | 法案生命周期 | `site:congress.gov space OR semiconductor OR commercial space <window>` |
| Federal Register | 行政规则草案 | `site:federalregister.gov satellite OR commercial space OR export controls <window>` |
| FERC | 数据中心并网/电网 | `site:ferc.gov large load OR data center <window>` |
| SEC EDGAR Full-text | S-1 / 8-K / Form D | `site:efts.sec.gov S-1 OR 8-K space OR satellite OR semiconductor <window>` |
| FAA | 发射许可 / mishap | `site:faa.gov launch OR mishap OR investigation <window>` |
| FCC | 卫星市场进入 / D2D | `site:fcc.gov satellite OR D2D OR direct-to-cell <window>` |
| 巨潮资讯 (cninfo.com.cn) | 中国上市公司公告 | `site:cninfo.com.cn 商业航天 OR 卫星 OR 太空 <window>` |
| 上交所 / 深交所 / 港交所 | 上市公司公告与并购 | `site:sse.com.cn OR site:szse.cn OR site:hkexnews.hk 卫星 OR 商业航天 <window>` |
| CNSA / MIIT / NDRC / SASTIND | 中国部委原文 | `site:cnsa.gov.cn OR site:miit.gov.cn 商业航天 OR 太空算力 <window>` |
| arXiv | 论文层信号 | `site:arxiv.org space compute OR onboard AI OR satellite inference <window>` |

## 工作流程

阶段 1（扫描计划 + 三 Pass 执行）执行步骤：

1. 把时间窗口归一为 ISO 起止日期与本周编号 `YYYY-Wxx`。
2. 按"维度 1 + 维度 4"先生成 12-15 条结构化查询，全部进扫描清单。
3. 把"维度 2"前 12 家公司做模板化查询追加。
4. 视当周板块活跃度从"维度 3"补 5 条邻接查询。
5. **执行 Pass A**：逐条调用 WebSearch，记录每条查询字符串与命中数。
6. **执行 Pass B（全量必扫，HARD MANDATORY）**：先运行 `scripts/build_pass_b_required.py` 生成策展清单 ∪ `source_map.csv` 有效 S_Core URL 的并集，得到 `pass_b_total_required` 与 `pass_b_required_urls`；然后对 `pass_b_required_urls[*].url` **逐条** WebFetch，每条记录 status (ok / blocked / empty) 和 hits。`blocked` 必须先尝试 RSS / 备用页 / `site:` 替代查询，三种替代都失败才允许标记关闭。
7. **输出 Pass B 完成度 JSON**（schema 见上文 Pass B 段末尾）。`pass_b_total_required` 必须等于脚本输出，`pass_b_attempted` 必须等于 `pass_b_total_required`，否则回到第 6 步补扫，不允许进入 Pass C。
8. **执行 Pass C**：对 Pass A + Pass B 合并去重后的候选 URL 逐条 WebFetch 验证原文，写入事件库。
9. 在阶段日志中列出每条实际执行的查询词与每个 Pass B URL 的状态；用户可补加，但不能减。

阶段 2（建立事件池）执行步骤：

1. **覆盖优先**：所有命中的事件先全部进事件库，不在搜索阶段做相关性筛选。
2. 标记 `source_discovery_flag = Yes` 的新发现来源。
3. 进入阶段 3-4 的去重、评分、同心圆判断决定 S/A/B/C 与是否入正文。

## 失败模式与排查

如果某周事件总数低于 Fail-Closed 阈值（事件表 < 80 / 候选 < 80 / `pass_a_query_count < 25` / `pass_a_hit_count < 30` / Pass B `pass_b_attempted < pass_b_total_required` / 正文 < 70 任一不达标），需排查：

- 查询是否被 LLM 折叠成更宽泛的词？显式打印每条实际执行的查询词回查。
- 是否所有查询都返回了空结果？按维度 4 强制重新跑一次专用入口查询。
- 是否同心圆边界判断过紧把候选事件丢在了搜索阶段？阶段 2 不应做相关性筛选，只在阶段 4 评分后剔除。
- 美国融资是否只查了企查查/数据库未查 PR Newswire/GlobeNewswire/SEC EDGAR？强制补做维度 4。
- 中文政策是否漏了央视/经济日报/上海经信委/国新办？维度 1 中追加 2-3 条带 `site:` 限定。

## 进阶：subagent 并行扇出（可选）

如果运行环境支持 subagent，可把维度 1-4 拆成 3-4 个并行 agent：

- 政策 agent：维度 1 政策类 + 维度 4 立法入口。
- 科技 agent：维度 1 科技类 + 维度 2 玩家清单 + arXiv。
- 融资 agent：维度 1 融资类 + 维度 4 SEC/交易所 + 企查查导入。
- 邻接 agent：维度 3 全部触发词。

每个 subagent 独立扇出 5-8 条查询，把结果回送主 agent 合并。子 agent 上下文隔离避免主 agent 提前归并查询。

## 检查清单

阶段 1 结束时确认：

- [ ] 实际执行查询条数 ≥ 25 条；
- [ ] 维度 1/2/3/4 都各满足下限；
- [ ] 玩家清单本周覆盖 ≥ 8 家；
- [ ] 政府/立法/交易所专用入口至少跑了 4 次；
- [ ] **Pass B 并集清单全部条目逐条 WebFetch 完毕**（策展清单 + `source_map.csv` 有效 S_Core URL 去重后的条数 = `pass_b_total_required`，由 `scripts/build_pass_b_required.py` 得到），每条状态记录在 Pass B 完成度 JSON（`pass_b_attempted == pass_b_total_required`）；
- [ ] **`source_map.csv` 中所有有效 `tier=S_Core` URL 都已出现在 `pass_b_urls` 中**；无有效 URL 的 S_Core 需列入 `source_map_s_core_skipped`。
- [ ] **Pass B 中 `blocked` 的 URL 已尝试 RSS / 备用页 / `site:` 三种替代**且失败才标关闭；
- [ ] 把每条实际执行的查询词与每个 Pass B URL 的状态记入扫描日志（便于复盘和对比下周）。

阶段 2 结束时确认：

- [ ] 事件库总数较扫描日志一一对应，没有"搜到但没入库"的事件；
- [ ] 美国融资单笔 ≥ 1 亿美元的并购/IPO 公告全部入库；
- [ ] 立法事件（MATCH/SCALE/CHIPS 等）有 GovInfo 或 Congress.gov 主来源；
- [ ] 美国大型科技事件（NASA/ISS/Falcon/Starlink/Vast/Blue Origin）有官方或 Spaceflight Now/SpaceNews 来源。
