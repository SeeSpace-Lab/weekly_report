# 周报系统工作流

当用户希望按步骤控制周报生成，而不是一次性生成最终稿时，使用本文件。

## 系统结构

输入层：

1. `source_map.csv`：信息源管理表（唯一格式）。
2. 公开来源：政策、技术、公司公告、交易所公告、产业新闻。
3. 手工融资清单（**两份**）：境内融资清单（无明确币种时默认 CNY，含「境内」/domestic）、境外融资清单（无明确币种时默认 USD，含「境外」/「海外」/overseas/global/foreign）。明确披露币种永远优先于默认值；两份均为企查查全行业全量数据，需要先按 `reporting-playbook.md` 的"全行业融资清单筛选"段做行业筛选。

   **网页获取限定**：若需要登录企查查网页生成或补齐这两份清单，只允许使用用户已登录的 Chrome 浏览器，按 `qcc-chrome-workflow.md` 操作。禁止使用 Codex 内置浏览器访问企查查；Chrome 不可用或认证受阻时必须停下请求用户处理或导出文件。
4. 历史数据库：过往事件库、公司库、历史周报。

处理层：

1. 信息抓取与去重。
2. 分类与 S/A/B/C 评分。
3. 周报生成与信息源地图更新。

输出层：

1. 太空算力产业周报。
2. 更新后的事件库和信息源地图更新建议。

核心原则：每周周报不是一次性文档，而是持续更新的产业情报系统。

## 阶段门

### 阶段 0：输入检查

先检查本周工作文件夹。如果必要输入缺失，停止分析并提示用户补齐。

公开信息扫描的最低输入：

- 信息源地图：`source_map.csv`（唯一格式）。
- 时间窗口：开始日期和结束日期（详见下文"时间窗口规则"）。

#### 时间窗口规则（强约束）

每次运行必须先锁定时间窗口，事件纳入与排除完全以此为准。

| 项 | 规则 |
|---|---|
| 输入格式 | 内部统一为 ISO `YYYY-MM-DD`；用户可传"YYYY年M月D日 – YYYY年M月D日"、"Wxx"或"本周"，skill 必须归一为 ISO 起止日期。 |
| 窗口闭区间 | `[start_date, end_date]` 含两端。事件 `date` 必须落在区间内才能进入事件池。 |
| 时区与截止 | 默认 Asia/Shanghai；`start_date 00:00:00` 至 `end_date 23:59:59`。之后发生的事件归下一周。 |
| 周编号 | 采用 ISO 8601 周（周一为周首），格式 `YYYY-Wxx`（如 2026-04-13 至 2026-04-19 → `2026-W16`）。 |
| `date` vs `published_date` | 默认以"事件发生日期"`date` 是否在窗口内为准。若 `date` 在窗口外、`published_date` 在窗口内：原则上排除，不进正文；如该事件具有 S/A 信号且本周才公开披露，可在 `analyst_note` 标注"延迟披露"后纳入下周。 |
| 历史周补做 | 用户明确指定历史窗口（如"帮我生成 2026 年 4 月 13 日 – 2026 年 4 月 19 日的周报"）时，按指定窗口严格筛选；标题块的"整理日期"用今天，"时间窗口"用指定窗口；事件库 `date` 必须严格落在指定窗口。 |
| 跨日事件 | 同一事件不同来源给出的日期不一致时，以官方/公司一手公告日期为准；记录在 `analyst_note`。 |
| 跨周事件 | 跨多日动作（如多日会议、连续多日采购公告）以"主要动作发生日"作为 `date`；如主要日期在窗口外，归下一周。 |

如果用户没有明示时间窗口，必须停下来询问，不要默认"本周"或自动取最近 7 天。

完整周报系统的额外输入：

- 手工融资导出（**两份缺一不可**）：
  - **境内融资清单**：文件名包含「境内」或 `domestic` + `融资`/`企查查`/`工商`/`qcc`/`financing`/`funding`/`股东` 等关键词；无明确币种时默认人民币。
  - **境外融资清单**：文件名包含「境外」「海外」、`overseas` / `global` / `foreign` + 上述融资关键词；无明确币种时默认美元。
  - 格式 `.xlsx`、`.csv` 或 `.tsv`；两份均为企查查全行业全量数据。
- 历史事件库：`event_database.xlsx` 或 `event_database.csv`。
- 过往周报：Markdown、DOCX、PDF 或历史周报文件夹。

如果两份融资清单中任一缺失，提示：

`缺少 <境内/境外> 融资清单，无法生成对应侧的完整融资模块。请把企查查导出的 <境内/境外> 融资 list 放入本周文件夹（文件名含相应关键词）；如果本轮只做公开信息草稿且明确放弃该侧融资模块，请确认。`

用户要求由 agent 补齐网页数据时，先检查 Chrome 控制能力与登录状态；不要打开 Codex 内置浏览器。Chrome 登录、验证码或访问限制必须由用户处理，agent 不得读取 cookie、复制会话或绕过限制。

入库前必须按 `reporting-playbook.md` 的"全行业融资清单筛选"段做行业筛选预处理；不允许把全量原表直接灌进事件库。

### 阶段 1：扫描计划

按以下顺序生成本周扫描清单：

1. 从 `source_map.csv` 中筛选 `tier = S_Core` 作为每周固定扫描池。
2. 视当周板块活跃度加入 `tier = A_Active` 来源。
3. 关键词、玩家清单与搜索扇出规则按 `references/search-playbook.md` 的 4 维度执行。

扫描矩阵：

- 中国 × 政策
- 中国 × 科技
- 中国 × 融资
- 美国 × 政策
- 美国 × 科技
- 美国 × 融资
- 其他国家 S/A 级例外池

搜索关键词必须覆盖 `source_map_rules.md` 中的中英文太空算力关键词。

### 阶段 2：事件池

所有发现先进入事件表，再写周报。不要直接从搜索结果写正文。

公开扫描命中的事件（Pass A/B/C）必须 100% 全员入库（参 SKILL.md 阶段 2 全员入库硬规定）；**手工融资清单需先做行业筛选**——境内/境外两份原表都是全行业全量数据，按 `reporting-playbook.md` 的"全行业融资清单筛选"段判定哪些条目"必入"、"边界"、"直接丢弃"，把通过的条目按 `manual_financing_import_template.csv` 字段写入事件池。

事件库空表头模板见 `event_database_template.csv`。

事件表字段：

| 字段 | 说明 |
|---|---|
| `event_id` | 稳定事件编号，例如 `2026W20-US-POL-001`。 |
| `date` | 事件发生日期或可确认的最佳日期。 |
| `published_date` | 来源发布日期；可与 `date` 相同。 |
| `country` | China、US、Global、Europe、Japan、Other 或 China-US。 |
| `sector` | Policy、Technology 或 Financing。 |
| `domain` | Space_Compute、AI、Chip、Commercial_Space；可用分号多选。 |
| `entity` | 公司、机构、项目、计划或交易主体。 |
| `event_title` | 简短事实标题。 |
| `event_summary` | 事实摘要，不写未经验证的判断。可容纳同一公告/任务/交易中的多个关键参数，避免把子事实拆成多条事件。 |
| `source_name` | 主来源名称。 |
| `source_type` | Official、Company、Industry_Media、Financial_Media、Database、Filing、Exchange、Think_Tank、Research_Institute、Wire_Service、Other。 |
| `source_url` | 主来源链接；手工导入可填 `N/A`。 |
| `source_tier` | 信息源地图中的 tier（S_Core / A_Active / Watch / Backup / Manual），未知则留空。 |
| `secondary_sources` | 可选，验证来源用分号分隔。 |
| `space_compute_relevance_score` | 太空算力相关性，1-5 分（权重 50%）。内核 5；中圈载体 3-4；外圈关联 2-3；勉强外圈 1。 |
| `industry_impact_score` | 产业影响，1-5 分（权重 30%）。 |
| `novelty_score` | 新颖性，1-5 分（权重 20%）。 |
| `total_score` | 加权总分，1-5 分。证据强度由 `source_tier` 兜底，可行动性写在 `meaning_for_us`/`next_watch` 中，不单独打分。 |
| `priority` | S/A/B/C。 |
| `reason_for_priority` | 评级理由。 |
| `include_in_report` | Yes、Brief、Appendix、Database_Only 或 Exclude。 |
| `implication` | 对产业的含义。 |
| `meaning_for_us` | 对用户公司的意义。 |
| `next_watch` | 后续跟踪点。 |
| `analyst_note` | 人工备注或待核查事项。 |
| `source_discovery_flag` | 如果来源不在信息源地图中，填 Yes。 |

## 分类规则

每条事件必须有一个主板块：

- 政策：政府政策、产业规划、军工采购、航天监管、频谱/轨道资源、卫星互联网政策、AI/芯片政策、出口管制、政府项目和预算。
- 科技：太空算力、星上计算、星载 AI、卫星互联网、遥感 AI、星间链路、星地协同、空间数据中心、抗辐照芯片、卫星载荷、低功耗 AI 芯片、发射、卫星平台。
- 融资：股权融资、工商变更、新增股东、注册资本变化、并购、IPO/SPAC、战略投资、政府基金、产业资本、订单融资信号。

领域标签：

- 太空算力：星上计算、星地协同、空间边缘云、空间数据中心、卫星云计算。
- AI：遥感 AI、星载 AI 推理、多模态感知、自动任务规划、空间智能体。
- 芯片：抗辐照芯片、星载 CPU/GPU/FPGA/ASIC、RISC-V、存算一体、低功耗 AI 芯片。
- 商业航天：卫星制造、低轨星座、火箭发射、遥感星座、卫星通信、地面站、星间链路。

## 手工融资导入

企查查每周提供两份全行业融资清单：境内 + 境外，均为完整周报的必要输入。明确币种优先；无明确币种时境内默认 CNY、境外默认 USD。来源原文必须保留。**两份清单都不能直接灌进事件库**——必须先按 `reporting-playbook.md` 的"全行业融资清单筛选"段判定行业归属（必入 / 边界 / 直接丢弃），把通过的条目按下表字段写入事件池，未通过的条目保留原 Excel/CSV 作为审计副本即可。

空表头模板见 `manual_financing_import_template.csv`。

| 字段 | 说明 |
|---|---|
| `company_name` | 企业主体或常用公司名。 |
| `date` | 融资或工商变更日期。 |
| `event_type` | Financing、shareholder change、registered capital change、external investment、M&A、IPO、government fund、contract signal。 |
| `amount` | 双货币展示字符串，如 `RMB 5亿元（约 USD 69.8M）`；由金额审计列生成，原始币种在前。 |
| `amount_original` | 来源披露的原始金额文本，不改写精度。 |
| `currency_original` | 原始币种 ISO 代码，如 `CNY`、`USD`、`EUR`。 |
| `amount_rmb` | 人民币对照金额；模糊金额保持同等近似语义。 |
| `amount_usd` | 美元对照金额；模糊金额保持同等近似语义。 |
| `fx_rate_usd_cny` | 本次换算采用的 USD/CNY 汇率。 |
| `fx_rate_date` | 汇率日期；优先事件日，非交易日取最近前一交易日。 |
| `fx_source` | 汇率来源，优先央行/官方基准来源。 |
| `investors` | 投资方，如有。 |
| `new_shareholders` | 新增股东，如有。 |
| `registered_capital_change` | 注册资本变化，如有。 |
| `business_direction` | AI 补充的业务方向。 |
| `value_chain_position` | AI 判断的产业链位置。 |
| `space_compute_relevance` | High、Medium、Low 或 None。 |
| `priority` | S/A/B/C。 |
| `notes` | 人工或 AI 备注。 |

AI 处理步骤：

1. 清洗公司名称并合并重复公司。
2. 判断公司业务方向。
3. 映射到产业链环节。
4. 判断与太空算力 / AI / 芯片 / 商业航天的相关性。
5. 结合融资规模、投资方质量、公司赛道、战略相关性和证据强度打分。
6. 对重点融资事件，尽量用企查查、IT 桔子、36 氪、投资界、公司公告、交易所公告或官方发布中的至少两个来源交叉验证。
7. 同时保留原始币种金额与 RMB/USD 对照金额；境内评级和金额门槛使用 `amount_rmb`，境外使用 `amount_usd`，确保同一市场内可比。

如果缺少其中任一份清单（境内或境外），不生成对应侧的完整融资模块；只能在用户明确授权后生成"公开信息草稿版"，并在报告开头标注缺失侧（如"境内手工融资数据缺失"）。

优先级示例：

- 普通外围商业航天公司小额融资：B。
- 星载 AI 芯片公司获得国家队或产业资本投资：A。
- 潜在竞争对手获得大额融资、关键客户或国家队背书：S。

## 来源发现

公开扫描时，如果发现新来源，按以下条件判断是否纳入信息源地图：

1. 连续出现高相关信息；
2. 首发重要事件；
3. 是未入库的官方、公司或数据库来源；
4. 覆盖现有信息源地图没有覆盖的细分方向；
5. 信息质量高且更新稳定。

新增来源默认进入 `Watch`。只有持续产生有效信号，或本身是官方/监管/交易所来源，才建议升级 `S_Core` 或 `A_Active`。低价值、转载站、噪音、连续失活来源进入 `Backup`，并在 `notes` 中标注 "noise" / "deprecated" / "merged into <id>"；不再使用 `Noise` 状态枚举。

信息源地图更新建议表：

| 字段 | 说明 |
|---|---|
| `source_name` | 建议新增或更新的来源。 |
| `country` | China、US、Global、Europe、Japan、Other。 |
| `category` | Policy、Technology、Financing、Chip_AI_Compute、Market_Background。 |
| `source_type` | Official、Company、Media、Database、Filing、Exchange、Think_Tank、Research_Institute、Other。 |
| `url` | 稳定的来源主页或栏目页。 |
| `suggested_priority` | S/A/B。 |
| `suggested_status` | S_Core、A_Active、Watch、Backup、Manual（与 source_map.csv 的 `tier` 字段保持一致；噪音/转载/失活归 Backup + notes 标注）。 |
| `reason` | 新增、升级、降级或删除理由。 |

## 输出模式控制

`老板版`：

- 一页纸；
- 3 条核心结论；
- 只写 S/A 级事件；
- 必须写清楚影响和建议动作。

`完整版`：

- 标题块；
- 核心结论；
- 按重要性排序的 S/A 级事件；
- 政策、科技、融资三大模块；融资板块（5C.1+5C.2+5C.3）合计条数 **≤ 正文总条数 × 30%**（HARD RULE，详见 `reporting-playbook.md`"融资占比 ≤ 30% HARD RULE"段）；
- 信息优先级表；
- 信息源地图更新建议；
- 下周重点跟踪。

`数据库版`：

- 结构化事件表；
- 保留 S/A/B 事件和必要的 C 级事件；
- 保留评分字段。

如果用户要求三种输出，顺序为：先生成数据库版，再生成老板版，最后生成完整版。
