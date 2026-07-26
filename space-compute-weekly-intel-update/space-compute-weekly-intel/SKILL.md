---
name: space-compute-weekly-intel
description: 用于运行分阶段的中美太空算力产业周报工作流。适用于检查必要输入文件、读取信息源地图、导入企查查或融资清单、建立事件库、进行 S/A/B/C 评分、生成太空算力/星载 AI/芯片/AI 基础设施/商业航天周报，以及更新信息源地图。
---

# 太空算力产业周报工作流

把周报视为持续更新的产业情报系统，不是一次性新闻汇总。默认覆盖中国和美国；其他国家只在出现 S/A 级或能补充中美对照判断时纳入。

主航道（锚点）：**太空算力**——星上计算、星载 AI、空间数据中心、星地协同算力、宇航级算力芯片。所有事件以"它对太空算力主航道的影响"为锚点判断纳入与优先级。

覆盖范围（同心圆，2026 已放宽）：

- 内核：太空算力、星载 AI、抗辐照/宇航级算力芯片、空间数据中心。
- 中圈：低轨星座、遥感星座、卫星互联网、星间链路、地面站、卫星制造与发射、商业空间站（Vast / Axiom / Sierra Space）、ISS 科研载荷、商业发射、NASA Commercial Crew/CRS、可复用火箭里程碑——太空算力的载体与链路。
- 外圈（2026 默认纳入候选，由阶段 4 评分决定去留，不在搜索阶段过滤）：地面 AI 芯片、AI 算力基础设施、AI 数据中心、CPO/光互连、AI 芯片出口管制、AI 算力政策（国家级与地方）、半导体高端制造、车规级 SoC。
- 排除：消费电子、与空间/算力/数据/AI 芯片无关的泛 AI 模型新闻、纯营销稿。

**事实覆盖面 = "商业航天 × AI 算力 × 芯片政策"三领域交集。** 任何"过早用太空算力主航道砍掉外圈"的做法都是错误的；纳入边界的最终裁判是 `references/reporting-playbook.md` 同心圆 + 金额兜底规则，不是搜索阶段的 LLM 主观判断。

一级板块：政策 / 科技 / 融资
领域标签：太空算力 / AI / 芯片 / 商业航天

合格阈值（正文 ≥ 70 / 事件表底量 ≥ 80 / 融资占比 ≤ 30% / 各板块下限）与不达标时的回退路径见 `references/reporting-playbook.md` 的"回归基准（Regression Baseline）与质量阈值"段。**W16（正文 78 条、事件表 100+）只是容量参照，不是合规模板**——W16 融资 41/78 ≈ 53% 在新口径下属于超标反例，新流程必须满足融资 ≤ 30%。任何指标低于阈值视为执行不达标，必须回到对应阶段复跑。

## 必须采用分阶段模式

除非用户明确要求"端到端一次性跑完"，否则必须分阶段推进。每完成一个阶段，先交付当前阶段产物，并提示用户确认、补充文件或修正判断，再进入下一阶段。

如果必要输入缺失，必须停下来说明缺什么、建议文件名是什么、应放在哪个文件夹。不要编造融资数据、历史事件、历史周报或信息源地图更新。

## 输入检查

每次周报运行前，先检查：

- `source_map.csv`：信息源管理表（**唯一格式**——已弃用 xlsx 并存方案，所有脚本与文档只读 csv）。**fallback 规则**：本周文件夹未提供 `source_map.csv` 时，`scripts/check_inputs.py` 会自动 fallback 到 skill 内置的 `references/source_map.csv`，这种 fallback **不算缺文件**——可以正常进入阶段 1。仅当本周文件夹有自定义 `source_map.csv`（覆盖 skill 默认值）时才使用本周版本。
- 企查查 / 融资 / 工商变更导出文件：完整周报的必要输入，**必须同时提供两个文件**——
  - **境内融资清单**（文件名含「境内」或 `domestic`）：无明确币种时默认人民币；明确披露其他币种时以披露币种为准，并换算为人民币分析口径。
  - **境外融资清单**（文件名含「境外」「海外」或 `overseas` / `global` / `foreign`）：无明确币种时默认美元；明确披露其他币种时以披露币种为准，并换算为美元分析口径。
  两个清单都是全行业全量数据，需要按 `references/reporting-playbook.md` 的"全行业融资清单筛选"段先做行业筛选，再按 `manual_financing_import_template.csv` 字段入事件池。任一文件缺失时必须提醒用户补齐；只有用户明确确认"本轮跳过对应模块"才允许放行。
- **企查查 Chrome-only HARD RULE**：需要从企查查网页补齐或筛选清单时，只使用用户已登录的 **Chrome 浏览器**；禁止使用 Codex 内置浏览器访问企查查。Chrome 控制不可用、Chrome 未登录、页面触发验证码/访问限制时，停下来让用户处理或请用户导出文件，不得自动切换回内置浏览器。完整流程见 `references/qcc-chrome-workflow.md`。
- **企查查页面上下文主流程 HARD RULE**：无法使用用户提供文件或网站正常导出时，在已登录的 Chrome 页面中复用页面自身请求契约，按页调用融资列表接口并保存 Raw CSV，再运行 `scripts/convert_qcc_raw_financing.py` 生成 21 列标准化 CSV。只使用相对路径和页面现有登录态，不复制 cookie，不构造绕过验证的签名；每次请求间至少等待约 `500ms`。页面接口不可用时，才使用 UI 逐页读取作为 fallback。完整流程见 `references/qcc-chrome-workflow.md`。
- **融资金额转换 HARD RULE**：Raw CSV 永远保留来源原始金额文本。标准化 CSV 保留原 14 列，并追加 `amount_original`、`currency_original`、`amount_rmb`、`amount_usd`、`fx_rate_usd_cny`、`fx_rate_date`、`fx_source`。明确币种优先；无币种时境内默认 CNY、境外默认 USD。境内规模分析和金额门槛统一使用 `amount_rmb`，境外统一使用 `amount_usd`；模糊金额保留原精度，未披露金额不推算。
- `event_database.xlsx` 或 `event_database.csv`：当用户要求历史去重、趋势延续或事件沉淀时使用。
- 过往周报：当用户要求延续上周跟踪、做趋势比较或检查重复事件时使用。
- **国内轨中文搜索 MCP（双轨检索）**：`scripts/check_inputs.py` 会输出 `cn_search_mcp.installed`。我的 WebSearch 为 **US-only**，缺中文搜索 MCP（如 `bocha` 博查）会导致中国政策/融资召回不全（CN 政策轴覆盖不足）。**`installed=false` 时必须先停下来提示用户安装**（安装方式见 `references/search-playbook.md`「双轨检索」段）；用户明确选择 fail-soft 继续时才放行，并在交付第四章「密度说明」标注"国内轨 MCP 缺失，CN 覆盖依赖 WebSearch + 手工补料"。

如果用户提供了本周工作文件夹，优先运行：

```bash
scripts/check_inputs.py <本周文件夹>
```

如果用户明确要求"本轮先跳过企查查/融资导入，只做公开信息草稿"，才允许运行：

```bash
scripts/check_inputs.py <本周文件夹> --allow-missing-financing
```

## 分阶段工作流

### 阶段 0：确认范围与缺文件检查

先确认：

- **时间窗口（强约束）**：必须拿到明确的开始日期和结束日期，归一为 ISO `YYYY-MM-DD`，并算出 ISO 周编号 `YYYY-Wxx`。如果用户未明示，停下来询问，不要默认"本周"或自动取最近 7 天。事件 `date` 严格落在 `[start, end]` 闭区间才能进入事件池。详细规则与跨日/跨周/延迟披露处理见 `references/weekly-system-workflow.md` 的"时间窗口规则"段。
- 覆盖范围：中国、美国，是否纳入 S/A 级国际补充。
- 输出模式：`老板版`、`完整版`、`数据库版`，或三者都要。
- 是否已提供境内 + 境外两份手工融资清单（缺一不可）；如缺失必须提示补齐或由用户明确确认本轮只做公开信息草稿（注明缺哪一侧）。
- 若缺失清单且用户希望从企查查网页补齐：确认可控制用户的 Chrome 且其中已登录企查查；禁止用 Codex 内置浏览器试探或代替 Chrome。Chrome 不可用时停止并请求用户打开/登录 Chrome 或导出文件。
- **国内轨检索 MCP 是否就绪**：看 `check_inputs.py` 输出的 `cn_search_mcp.installed`。为 `false` 时**停下来提示用户安装 `bocha`（博查）中文搜索 MCP**，说明不装会使 CN 政策/融资召回不全；用户可选 fail-soft 继续（按 `search-playbook.md`「双轨检索」段处理并在交付标注），但**不得因此降低任何覆盖阈值**。
- 是否需要使用历史事件库或过往周报做去重。

按需读取参考文件（**懒加载**：进入对应阶段时才读，不要一次全读）：

- `references/weekly-system-workflow.md`：阶段门、必要输入、事件库字段、融资导入、来源发现、时间窗口规则。
- `references/search-playbook.md`：搜索扇出强约束、四维度查询模板、领域玩家清单、政府/交易所专用入口、三 Pass 工作流、Fail-Closed 合规门、Pass B 完成度 JSON schema。**阶段 1 进入前必读。**
- `references/source_map_rules.md`：source priority、每周高频池、扫描顺序、搜索模式、维护规则。
- `references/reporting-playbook.md`：同心圆与外圈两层规则、S/A/B/C 评分、金额兜底、事件原子粒度与反拆条规则、去重、证据强度、回归基准、质量检查。**阶段 4 进入前必读。**
- `references/output-template.md`：老板版、完整版（含一/二/三/四/五/六章结构）、数据库版输出模板（**结构定义层**）。**阶段 5 进入前必读。**
- `references/boss-html-design.md`：老板版 HTML 视觉设计源文件。仅当用户要求 `老板版HTML`、网页化老板版、HTML 周报或需要修改 HTML 视觉时读取；读取后按其中 design tokens / hard rules 执行，内容选择和保存路径仍以 `output-template.md` 与 `reporting-playbook.md` 为准。
- `references/w23-boss-html-baseline.md`：老板版 HTML 的固定母版契约。用户要求沿用 W23 或未另行指定视觉基准时必读；它规定 W23 的不可漂移结构、首屏口径、判断写法、融资摘要与自动校验。
- `references/qcc-chrome-workflow.md`：企查查网页采集与融资清单整理的 Chrome-only 流程。只要需要访问企查查网页就必须读；禁止使用 Codex 内置浏览器。
- `assets/`：**真实历史成品参考实例**（W20 周报三种版本，**实例层**），不是结构定义。**阶段 5 生成具体版本时按需读对应实例**：
  - `assets/中美太空算力周报_2026-W20.md`：完整版 Markdown 范例（六大章 + 板块表格 + 主线总结的具体写法、详简程度、判断密度）。
  - `assets/老板版_2026-W20.html`：老板版 HTML 范例（design tokens 已落地的真实样式、card 结构、底部三栏的实际呈现）。
  - `assets/event_database_2026-W20.csv`：数据库版范例（26 列字段、分号多值、`source_type` / `source_tier` 等枚举的真实写法）。
  
  **冲突优先级**：`output-template.md` / `reporting-playbook.md` / `boss-html-design.md` 是**规则层**（说该怎么做），`assets/` 是**实例层**（展示某一周真实做出来的样子）——规则与实例冲突时**以规则为准**，assets 仅作"风格/详简程度/字段填法"的具体参照。不允许直接复制 W20 的事件清单或文字到本周交付。

### 阶段 1：扫描计划 + 三 Pass 执行

从 `source_map.csv` 中筛选生成本周固定扫描清单：

- `tier = S_Core`（每周固定扫的核心一手来源）
- 当本周对应板块活跃时，把 `tier = A_Active` 的来源加入扫描清单
- `tier = Manual` 的来源（如企查查）优先由用户导入文件；确需网页补齐时仅使用已登录的 Chrome，按 `qcc-chrome-workflow.md` 执行

**进入阶段 1 前必须读 `references/search-playbook.md`**——该文件定义了完整的搜索扇出强约束、4 维度 ≥25 条查询模板、Pass A/B/C 三遍工作流、Pass B 必扫集合（**本文件策展清单 ∪ `source_map.csv` 中全部有效 `tier=S_Core` URL**）、`scripts/build_pass_b_required.py` 生成方式、Pass B 完成度 JSON schema、Fail-Closed 合规门与五项证据要求、严禁兜底路径。SKILL.md 不重复这些细节，但下面三条契约层规则**永远高于**任何细节解读：

#### 契约层 HARD RULE（不可被任何细则放宽）

**1. Pass B 全量必扫，HARD MANDATORY，不可跳过、不可裁剪、不可分模式降级。** 全量基准由 `scripts/build_pass_b_required.py` 生成，必须等于 `search-playbook.md` 策展清单与 `source_map.csv` 中全部有效 `tier=S_Core` URL 的去重并集。不存在"时间预算紧 / 用户没要求那么多 / 用户先要个简版看看"等任何合法跳过 Pass B 的路径。并集清单上的全部 URL 必须逐条 WebFetch，每条返回 `ok` / `blocked` / `empty` 三态之一并写入 Pass B 完成度 JSON（schema 见 search-playbook.md）。`blocked` 必须先尝试 RSS / 备用页 / `site:` 三种替代，三种都失败才允许标关闭。`pass_b_attempted < pass_b_total_required` 或任一有效 S_Core URL 未出现在 `pass_b_urls` 中，均视为 Pass B 未完成，禁止进入 Pass C。

理由：Pass A（WebSearch）对官方/监管/交易所/IR 类来源（GovInfo、SEC EDGAR、CNInfo、SSE/SZSE、Vast/Axiom newsroom 等）系统性召不回，跳过 Pass B = 系统性放弃一手公告，必然导致金额兜底事件（并购/S-1/科创债/CRS 任务）漏报。

**2. 覆盖优先，后置过滤（coverage over filtering）。** 阶段 1-2 把所有命中的事件全部入库，不做任何形式的相关性筛选、同心圆筛选、主航道筛选——筛选只能发生在阶段 4 评分。

**3. 覆盖未达标 → Fail-Closed，唯一出路是回阶段 1-2 补扫。** 当 `pass_a_query_count < 25` / `pass_a_hit_count < 30` / Pass B `pass_b_attempted < pass_b_total_required` / 候选 < 80 / 事件池 < 80 / 正文 < 70 任意一项不达标时，按 `search-playbook.md` 的"Fail-Closed 搜索合规门"段输出"搜索未达标报告"并停止生成，**唯一允许的后续路径是补扫直到达标**——不存在"用户授权后降级生成简版"的兜底。**严禁**把不达标输出包装成完整版交付、用"事件密度低"作为不补扫理由、把搜索未达标报告伪装成正文"四、主线总结"段、自我判定"时间紧"跳过 Pass B、用"用户要轻量"作为放宽下限的理由。

**搜索阶段不存在任何"模式降级"概念**：所有阈值（Pass A query ≥ 25 / Pass A hit ≥ 30 / Pass B 全量 = 策展清单 ∪ 有效 S_Core URL 的脚本输出并集 / 候选 ≥ 80 / 事件池 ≥ 80 / 正文 ≥ 70 / 融资 ≤ 30% / 各板块下限）在所有情况下保持原值。`老板版` 与 `老板版HTML` 是输出形态（决定写多少、怎么排版），**不影响搜索覆盖与合规阈值**。

### 阶段 2：建立统一事件池

所有信息先进入事件表，再生成周报。不要直接从搜索结果写正文。事件表字段见 `references/weekly-system-workflow.md` 与 `references/event_database_template.csv`。

#### 全员入库（HARD RULE）

Pass A/B 命中且时间窗口落在本周的事件，**必须 100% 进事件表**。在阶段 2 不允许做任何形式的相关性筛选、同心圆筛选、主航道筛选。常见错误模式：

- ❌ "这条 AI 数据中心融资和星上算力关系不大，先跳过" → **必须入库**，由评分决定 B/C。
- ❌ "这条 ISS 科研载荷不直接命中星上算力" → **必须入库**，商业空间站/ISS 是中圈。
- ❌ "这条地方 AI 算力政策不在太空算力主航道" → **必须入库**，2026 年 AI 算力政策默认外圈纳入。
- ❌ "这条立法没点名航天" → **必须入库**，立法事件强制入正文（见 reporting-playbook.md 金额兜底）。

#### 入库流程

1. Pass A + Pass B 候选 URL/标题合并去重 → 候选事件清单。
2. 候选清单逐条 Pass C（WebFetch 验证）→ 抽 `date`、`published_date`、`entity`、`amount`、法案号/任务号 → 写事件库。
3. `date` 必须严格落在本周 ISO 闭区间内才允许进入事件池；窗口外但 `published_date` 在窗口内的延迟披露事件按 `weekly-system-workflow.md` 时间窗口规则处理。
4. `source_url` 保留原文链接，按来源类别填 `source_tier`。
5. **所有事件初始 `include_in_report` 为空**，由阶段 4 评分填入 Yes / Brief / Appendix / Database_Only / Exclude。

事件表底量阈值 **≥ 80 条**（含 B/C；高密度周 ≥ 100，参 `reporting-playbook.md` 回归基准段）。**阶段 2 完成时事件表 < 80 条即视为入库不足**，必须回阶段 1 触发 `search-playbook.md` Fail-Closed 合规门。**不存在 60 / 70 / 75 等中间档位**——任何 < 80 都是 fail，agent 不得自我说服"接近达标"。

企查查/融资清单（境内 + 境外）的行业筛选规则、字段映射、双货币保留、汇率审计与筛选自检比例见 `reporting-playbook.md` 的"全行业融资清单筛选"段。

#### Stage 2 Definition of Done JSON（HARD RULE）

阶段 2 完成、进入阶段 3 之前，必须打印以下 JSON 块。**该 JSON 中所有可从事件库推导的计数（`event_pool_count`、`source_tier_distribution`、`thresholds_check`）必须由 `scripts/compute_gates.py <event_db.csv> --week YYYY-Wxx --stage 2` 核算后照搬，禁止手算或目测自报**——只有 `candidate_count`、`time_window_excluded_count`、手工融资原表条数这几项事件库外的字段通过脚本参数传入或人工补：

```bash
scripts/compute_gates.py <事件库.csv> --week YYYY-Wxx --stage 2 \
  --candidate-count N --time-window-excluded N \
  --domestic-total N --domestic-kept N --overseas-total N --overseas-kept N
```



```json
{
  "stage": "2_event_pool_done",
  "week": "YYYY-Wxx",
  "candidate_count": <Pass A + Pass B 合并去重后的候选 URL 数>,
  "event_pool_count": <Pass C 验证后真正写入事件库的事件总数>,
  "time_window_excluded_count": <因 date 不在本周闭区间被剔除的事件数>,
  "manual_financing_imported": {
    "domestic_total": <境内原表条数>,
    "domestic_kept": <境内通过行业筛选写入事件池的条数>,
    "overseas_total": <境外原表条数>,
    "overseas_kept": <境外通过行业筛选写入事件池的条数>
  },
  "source_tier_distribution": {
    "S_Core": <N>, "A_Active": <N>, "Watch": <N>, "Backup": <N>, "Manual": <N>
  },
  "thresholds_check": {
    "event_pool_ge_80": <true/false>,
    "candidate_ge_80": <true/false>
  }
}
```

**违反方式**：① 不输出该 JSON 直接进入阶段 3-4；② 把 `event_pool_count` 写成估值（必须是已写入事件库的实数）；③ `event_pool_ge_80: false` 时仍进入下一阶段，而不是回阶段 1 触发 Fail-Closed。

`thresholds_check` 中任一为 `false` → 必须回阶段 1 补扫，不得进入阶段 3。`time_window_excluded_count` 显著偏高（> 候选数 30%）应自检时间窗口归一是否正确。

### 阶段 3：去重与验证

同一底层事件只保留一条事件记录。首选主来源顺序：

监管/政府原文 > 交易所公告/SEC/CNInfo > 公司公告/IR > 官方媒体 > 行业媒体 > 数据库 > 综合媒体 > 转载

媒体、数据库和工商变更可作为发现线索，但 S/A 级事件应尽量回到官方、公司、公告或权威数据库验证。

**事件原子粒度与反拆条规则**详见 `references/reporting-playbook.md` 的"事件原子粒度（防止同一新闻拆成多项）"段。核心原则：一条事件 = 一个独立决策 / 任务节点 / 交易 / 监管动作。**不得用子事实拆条来补足正文 ≥70、政策/科技/融资板块下限或融资 30% 占比**——条数不足必须回阶段 1-2 补搜或触发 Fail-Closed。

### 阶段 4：S/A/B/C 评级

**进入阶段 4 前必须读 `references/reporting-playbook.md`**——该文件定义了同心圆模型、外圈两层规则、3 维 1-5 分加权模型（太空算力相关性 50% / 产业影响 30% / 新颖性 20%）、等级阈值（S ≥ 4.30 / A 3.60-4.29 / B 2.80-3.59 / C < 2.80）、硬约束（相关性 ≤ 2 最高 B）、金额兜底（境外 ≥ 10 亿美元 / 境内 ≥ 100 亿元强制入正文）、立法兜底、证据强度兜底、融资占比 ≤ 30% HARD RULE 与压减优先级、融资条目正文 vs Database_Only 判定。

#### 阶段 4 强制停顿（HARD RULE，含 JSON gate）

AI 完成初评后，**生成 S/A 评级表必须停止本轮回复**，等用户明确回复"S/A 复核通过"或"调整以下条目"。**未收到回复前不得进入阶段 5。** 即使用户在同一轮请求里同时给出窗口、模式与"全跑完"指令，仍必须在阶段 4 停一次——这是为了防止 S/A 误判直接进入对外正稿。

**Stage 4 Review Gate JSON（与 Pass B 完成度 JSON 同等强度的机器 gate）**：S/A 评级表后必须打印以下 JSON 块再停止本轮回复。**该 JSON 必须由 `scripts/compute_gates.py <event_db.csv> --week YYYY-Wxx --stage 4` 核算后照搬**（脚本按 `include_in_report ∈ {Yes,Brief}` 判定正文、按 sector/country/domain 归口子板块、直接算出 `*_count`、`financing_ratio`、全部 `thresholds_check` 与 `all_pass`），杜绝"把 false 粉饰成 true"或估算虚高——脚本输出的是实数，不是 `*_estimate`。子板块多 domain 融资事件的单桶归属规则（芯片>商业航天>AI算力）见脚本头部注释：

```json
{
  "stage": "4_review_gate",
  "week": "YYYY-Wxx",
  "s_count": <S 级事件数>,
  "a_count": <A 级事件数>,
  "b_count": <B 级事件数>,
  "c_count": <C 级事件数>,
  "main_text_count_estimate": <预估正文条数 N>,
  "financing_in_main_count_estimate": <预估融资进正文条数>,
  "financing_ratio_estimate": "<X%>",
  "thresholds_check": {
    "main_text_ge_70": <true/false>,
    "financing_ratio_le_30": <true/false>,
    "policy_ge_14": <true/false>,
    "policy_cn_ge_7": <true/false>,
    "policy_us_ge_7": <true/false>,
    "tech_ge_13": <true/false>,
    "tech_cn_ge_5": <true/false>,
    "tech_us_ge_7": <true/false>,
    "tech_global_ge_1": <true/false>,
    "financing_ge_18": <true/false>,
    "fin_chip_ge_10": <true/false>,
    "fin_space_ge_5": <true/false>,
    "fin_ai_ge_3": <true/false>
  },
  "subsection_counts": {
    "policy_cn": <N>, "policy_us": <N>,
    "tech_cn": <N>, "tech_us": <N>, "tech_global": <N>,
    "fin_chip": <N>, "fin_space": <N>, "fin_ai": <N>
  },
  "awaiting": "user_signoff_or_adjust"
}
```

子板块下限来自 `output-template.md` 完整版结构段：政策中/美各 ≥ 7、科技中 ≥ 5 / 美 ≥ 7 / 跨国 ≥ 1、融资 5C.1 芯片 ≥ 10 / 5C.2 商业航天 ≥ 5 / 5C.3 AI 算力 ≥ 3。

**违反方式（视为严重违规）**：① 输出 S/A 表后未打印该 JSON 直接进入阶段 5；② 打印 JSON 后在同一轮回复内继续生成正文；③ 把 `thresholds_check` 中任意 `false` 项粉饰为 `true`；④ 不写 JSON、用一句"以下为 S/A 评级请复核"代替；⑤ **用宏数全 true（policy_ge_14 等）遮蔽子项 false（如 policy_us_ge_7=false）**——子板块下限与宏数下限同等强度，任一 false 都触发回退。

`thresholds_check` 中任一为 `false`，必须先回阶段 1-2 补覆盖或回阶段 4 复评，**不允许**直接请求用户授权进阶段 5。`*_estimate` 字段不是免责字段——若实际落稿后正文条数低于 `main_text_count_estimate` 超过 ±2 条，视为阶段 4 估算虚高，必须回阶段 4 重打 JSON。

### 阶段 5：生成周报

**进入阶段 5 前必须读 `references/output-template.md`**——该文件定义了三种输出版本的完整模板（老板版 Markdown / 老板版HTML / 完整版六大章 / 数据库版）、表格列、自检清单、保存路径、HARD CHECK 段。

**生成具体版本前按需读对应 assets 实例**（实例层，给"长什么样"的真实参照，不替代规则层）：

| 用户要求 | 必读规则层 | 必读实例层（assets） |
|---|---|---|
| 完整版 Markdown 周报 | `output-template.md` 完整版段 + `reporting-playbook.md` | `assets/中美太空算力周报_2026-W20.md` |
| 老板版HTML | output-template.md 老板版HTML 段 → reporting-playbook.md 老板版HTML 选择规则 → w23-boss-html-baseline.md → boss-html-design.md（按渐进披露顺序） | `assets/老板版_2026-W23.html`（默认母版）；W20 仅作旧实例参考 |
| 数据库版 csv | `output-template.md` 数据库版段 + `weekly-system-workflow.md` 事件库 schema | `assets/event_database_2026-W20.csv` |

assets 是 W20 真实成品，用于看"详简程度 / 判断密度 / 字段填法 / 视觉落地"。**严禁直接复制 W20 的事件、判断、HTML 数值到本周交付**——本周事件来自本周事件池，文字来自本周判断，assets 只用作风格参照。

阶段 5 写作总原则：报告要写**判断**，不要写信息源堆砌。完整性放进事件库，判断放进周报正文。仅生成用户要求的版本。

老板版HTML 渐进披露读取顺序（**按需逐级加载**）：① `output-template.md` 老板版HTML 段（内容/结构/事件选择/融资约束/保存路径/内容自检）→ ② `reporting-playbook.md` 老板版HTML事件选择规则段（哪些事件入选、融资压减）→ ③ `w23-boss-html-baseline.md`（固定母版、判断与统计口径、验证）→ ④ `boss-html-design.md`（颜色/字体/间距/Card Families/Hard Rules/Layout Rhythm Gate）。默认直接复用 `assets/老板版_2026-W23.html` 的 CSS 与 DOM 契约，不重新手写一套“相似”页面。

老板版HTML 将上一周摘要并入 proof object 底部，不设独立“上周回顾”标题或独立 section。只读取并概括紧邻上一周 `W(n-1)` 的真实周报，不延伸到更早历史；内容只设一个 `上周重点：`，用一段较完整摘要说明上一周最重要的产业变化，可点名关键主体与动作，但不写“本周进展”、问题核验、置信度评分或强行 follow-up 判断。摘要后保留 `<!-- PREVIOUS_WEEK_BUTTON -->` 占位符，按钮保持正常文档流，随摘要长度自然上下移动，禁止 absolute/fixed 定位或固定高度。

“老板版”只作为内部输出类型和文件名标识，不得出现在对外网页的 `<title>`、Open Graph / Twitter 分享标题、masthead、页面可见标题或分享摘要中。网页标题统一为 `中美太空算力周报 · YYYY-Wxx`；即使文件仍命名为 `老板版_YYYY-Wxx.html`，微信、浏览器标签和 GitHub Pages 分享卡片也不得显示“老板版”。

GitHub Pages 发布时把占位符生成成仅跨一期的双向导航：最新根页面 `index.html` 显示核心事件卡片形状的小按钮 `← W(n-1) 周报`，链接到已验证存在的上一周 HTML；紧邻上一周的历史页在同一位置显示 `W(n) 周报 →`，链接回根目录 `index.html`；更早历史周报只保留不可见占位符，不显示按钮。发布下一期前必须先清理上次生成的导航，再按新的“最新一期 ↔ 紧邻上一期”关系注入，避免旧按钮残留。按钮使用相对路径，不写“查看”，必须带真实 `<a href>`，并采用 `ivory-deep` 背景、1px `light-gray` 边框、8px 圆角、紧凑 padding、无阴影、非 pill；hover 时边框与文字切换为 `terracotta`，并保留清晰的键盘 focus outline。若找不到上一周文件，不注入按钮并明确报告缺失，不得编造或使用 `#` 占位。周次归属以被概括事件所在周为准：例如发布 W28 后，`index.html` 显示 `← W27 周报`，W27 历史页显示 `W28 周报 →`，W26 不显示导航。

老板版各一级板块之间统一使用 `65px` 留白；核心事件 dossier 内部 cards 之间继续保留 `48px`，不得随全局间距一起压缩。

老板版相邻周按钮必须通过 `boss_report_w23_renderer.py` 的 `adjacent_week_href` / `adjacent_week_label` 字段生成：最新一期使用 `← W(n-1) 周报`，紧邻历史页使用 `W(n) 周报 →`。渲染器母版已内置 `previous-button` 样式，周度脚本不得再用字符串替换追加按钮 CSS；链接目标必须在生成后做存在性验证。

老板版核心事件每张 card 的四个加粗字段标签必须统一渲染为 `判断 `、`影响 `、`对我们的意义 `、`后续跟踪 `：即 `</b>` 后保留一个半角空格再接正文。必须由 `scripts/boss_report_w23_renderer.py` 生成并校验，不得依赖周度生成器事后替换。

每周所有报告文件统一保存到 `<本周文件夹>/output/w{n}-reports/`，其中 `n` 为不补零的 ISO 周数字（例如 W27 → `w27-reports`）；老板版 HTML 保存为该目录下的 `老板版_YYYY-Wxx.html`。**不使用** `/mnt/user-data/outputs/`。

**老板版HTML 契约层硬规则（永远高于细节解读）**：通常每张 event card 必须以可点击的 `<a href="<source_url>" target="_blank" rel="noopener noreferrer">Source: <source_name> ↗</a>` 收尾，`source_url` 必须取自事件库 Pass C 验证过的真实 URL（**禁止编造 / 禁止 `#` 占位 / 禁止 `javascript:`**）；企查查高相关融资例外按本文件和 `reporting-playbook.md` 明示数据库来源。核心 cards 的 5-8 张只是一周常规编辑基线，不是强相关事件上限：所有评级为 S/A 且直接改变太空算力主航道判断、命中关键在轨验证/商业调用/政策许可，或直接涉及太空算力、太空数据、星载AI、能源、关键链路和可调用服务的事件必须全部进入核心区，数量不限。不得为增加数量纳入 B/C 或一般商业航天弱相关事件。

核心 cards 最终展示顺序首先按评级分层：完整展示全部 S 后，再展示全部 A。每个评级层内部按事件日期从早到晚；相同日期内按 `政策 → 科技 → 融资` 分组，同一板块的多张 cards 必须上下连续相邻。“分组”只调整卡片顺序，禁止把多个独立事件合并成一张 card；同级、同日、同板块内再按总分与证据强度排序。

### 阶段 6：信息源地图更新建议（含写入 gate）

完整版的"五、信息源地图更新建议"和"六、下周重点跟踪"是附加交付，每周仍需产出**建议清单（仅文档章节）**。详细字段、tier 分级与升降级条件见 `references/weekly-system-workflow.md` 来源发现段 + `references/source_map_rules.md`。

**生成建议清单（写在文档章节里）不需要用户授权**。**写入物理文件 `references/source_map.csv` 必须经过下面的 gate**——agent 不得用"用户已让我跑完阶段 6"或"建议清单已写在文档里所以可以同步到 csv"等措辞自我授权。

#### Stage 6 Source Map Write Gate JSON（HARD RULE）

在使用 Edit / Write 修改 `source_map.csv` 之前，必须先打印以下 JSON 块并停止本轮回复，等用户**明确**回复"批准写入"或"调整以下条目"：

```json
{
  "stage": "6_source_map_write_gate",
  "week": "YYYY-Wxx",
  "target_file": "references/source_map.csv",
  "pending_writes": [
    {"action": "add", "source_id": "...", "tier": "Watch", "url": "...", "reason": "本周发现的高质量一手来源"},
    {"action": "upgrade", "source_id": "...", "from_tier": "Watch", "to_tier": "A_Active", "reason": "连续 3 周产出 A 级事件"},
    {"action": "downgrade", "source_id": "...", "from_tier": "A_Active", "to_tier": "Backup", "reason": "近 8 周无有效信号"},
    {"action": "merge", "source_id": "...", "merged_into": "...", "reason": "镜像站/转载站"}
  ],
  "awaiting": "user_explicit_approval_to_write_csv"
}
```

**违反方式（视为严重违规）**：① 未打印该 JSON 直接 Edit/Write `source_map.csv`；② 打印 JSON 后在同一轮回复内继续写入 csv；③ 把"用户让我跑完阶段 6"解读为"包含写入授权"——阶段 6 的"建议清单产出"与"csv 物理写入"是两件事，写入必须独立授权；④ 把 `pending_writes` 截短或省略 reason 字段。

只生成文档章节而不写 csv 时，**不需要打印此 JSON**。本 gate 只在调用 Edit/Write 修改 source_map 物理文件前触发。

## 编辑与判断原则

- 周报正文服务于决策，不服务于穷尽罗列。
- 老板版常规编辑基线 5-8 条，但所有强相关 S/A 必须全量纳入且无数量上限；完整版按 `output-template.md` 板块下限 + `reporting-playbook.md` 金额/立法兜底，**整篇无上限**，事件密集周（W16 类）正文 ≥ 70 条；数据库版全量。**注：融资在完整正文中的总占比仍受 ≤30% 约束，但直接命中太空算力主航道或关键链路的 S/A 融资不受老板版默认融资 card 配额限制。**
- 完整性放进事件库，判断放进周报正文。
- 默认用中文写作；英文 source 名、公司名、项目名和技术术语按常用形式保留。
- 区分事件发生日期和来源发布日期。
- 不要把所有 AI、芯片、数据中心新闻都纳入。只有当它和卫星通信、太空算力、遥感 AI、出口管制、商业航天供应链、空间数据、国防采购或相关资本流向有关时才纳入。
- 其他国家动态默认只做补充，除非达到 S/A 级。
- 融资导入数据不是自证事实。企查查/工商变更作为 `Manual_Import` 线索，重要事件需交叉验证。
- **重要融资公开来源补全 HARD RULE**：企查查/手工清单只负责发现，不得把初始 `source_url=N/A` 当作“没有公开来源”。所有 S/A、所有拟进正文的 Yes/Brief、境内 ≥1亿元、境外 ≥1,000万美元，以及金额较小但直接命中太空算力/太空数据/星载AI/激光通信/宇航级芯片的融资，必须在评级和老板版选卡前按 `search-playbook.md`“手工融资来源补全门”执行公司名+金额/轮次、公司名+日期、公司名+投资方三类查询。找到公司公告、Newswire、投资方、政府或可信媒体页面后更新事件库主来源，把企查查降为交叉验证；只有记录了完整查询失败证据才可写“公开来源未找到”，严禁把“未继续搜索”包装成“缺少公开原文”。
- **融资覆盖以企查查为主、公开来源为验证**：融资板块的完整性、金额、轮次、投资方与工商变化以境内/境外企查查清单作为主数据底座，公开公告与媒体用于交叉验证和补充产业用途，不得因为公开搜索召回不足而丢弃企查查中的高相关事件。完成规定补搜后仍无公开 URL，但事件直接命中太空算力、太空数据、星载AI、激光通信、宇航级芯片或关键发射/链路基础设施时，可凭企查查记录进入正文、融资重点清单，S/A 事件也可进入老板版 card；必须在来源处明确写 `企查查（境内/境外）· 公开来源待补`，不得生成假链接或把数据库记录表述为公司公开确认。
- **老板版与独立融资产品分工**：老板版不制作逐笔“重点融资”列表；强相关 S/A 融资直接进入核心 cards，其余只用 H2 `融资其余条目` 写一段行业聚合摘要（原始清单→筛入数量→扣除 cards 后的芯片/商业航天/AI算力条数与金额区间→明细指向）。公司级完整融资清单、投资方、轮次、金额和来源以后单独生成《本周融资》。

## 信息源地图更新原则

- 新来源记录到组织/媒体/数据库层级，不记录一次性文章 URL。
- 新发现来源默认先进入 `Watch`，除非它是官方、监管、交易所或显然应每周扫描的核心来源。
- `source_map.csv` 用单一字段 `tier` 描述来源的扫描动作和生命周期状态，5 档：`S_Core` / `A_Active` / `Watch` / `Backup` / `Manual`。详细定义与升降级规则见 `references/source_map_rules.md`。
- `tier` 与事件优先级（event_priority = S/A/B/C）必须分开：前者描述来源价值与扫描动作，后者描述具体事件重要性。
- 合并镜像站、转载站和重复页面，优先保留原始来源。
- 不要因为某个来源产生过一次重要事件就直接升级为 `S_Core`；除非它本身是官方/监管/交易所，否则需要观察持续信号质量。

## 参考文件

- `references/weekly-system-workflow.md`：分阶段流程、必要输入、事件库 schema、融资导入、来源发现、时间窗口规则。
- `references/search-playbook.md`：搜索扇出与领域玩家词表、三 Pass 工作流、Pass B 必扫清单、Pass B 完成度 JSON、Fail-Closed 合规门。**阶段 1 必读。**
- `references/source_map.csv`：结构化信息源地图（唯一格式，所有脚本与文档以此为准）。
- `references/source_map_rules.md`：信息源地图使用规则、扫描顺序和搜索模式。
- `references/reporting-playbook.md`：同心圆、外圈两层规则、评分、去重、事件原子粒度、金额/立法兜底、融资 ≤ 30% HARD RULE、回归基准、质量检查清单。**阶段 4 必读。**
- `references/output-template.md`：老板版、完整版、数据库版模板。**阶段 5 必读。**
- `references/boss-html-design.md`：老板版 HTML 视觉设计源文件，仅在生成或修改 `老板版HTML` 时读取。
- `references/w23-boss-html-baseline.md`：W23 老板版母版契约与回归校验规则；老板版 HTML 必读。
- `references/qcc-chrome-workflow.md`：企查查 Chrome-only 页面上下文接口主流程、Raw/标准化落盘、UI fallback 与审计规则；访问企查查网页时必读。
- `references/event_database_template.csv`：事件库空表头模板（schema only）。
- `references/manual_financing_import_template.csv`：手工融资导入空表头模板（schema only）。
- `assets/中美太空算力周报_2026-W20.md`：完整版 Markdown 真实成品范例（实例层，阶段 5 生成完整版时按需读）。
- `assets/老板版_2026-W20.html`：老板版 HTML 真实成品范例（实例层，阶段 5 生成老板版HTML 时按需读）。
- `assets/老板版_2026-W23.html`：老板版 HTML 默认视觉母版；后续周报继承其 CSS、DOM 类名、首屏、卡片节奏与行动备忘结构。
- `assets/event_database_2026-W20.csv`：数据库版真实填充范例（实例层，含 26 列字段已填具体值的样例）。
- `scripts/check_inputs.py`：输入文件检查脚本。
- `scripts/convert_qcc_raw_financing.py`：把企查查页面接口 Raw CSV 确定性转换为 14 个业务字段 + 7 个金额审计字段；保留原金额，按境内/境外默认币种及明确披露币种生成 RMB/USD 数值列。
- `scripts/build_pass_b_required.py`：Pass B 必扫 URL 并集生成脚本（`search-playbook.md` 策展清单 ∪ `source_map.csv` 有效 S_Core URL）。
- `scripts/compute_gates.py`：**确定性核算阶段 2/4 阈值 gate JSON**（从事件库 CSV 直接算计数与 `thresholds_check`，替代 agent 自报）。阶段 2/4 打印 gate 前必跑。
- `scripts/render_db_csv.py`：**数据库版导出器**——校验 26 列 schema / 枚举 / 必填 / event_id 唯一性，规范化多值字段，按 priority+date 排序后写出合规数据库版 CSV。阶段 5 出数据库版时用。
- `scripts/boss_report_w23_renderer.py`：从 W23 资产逐字节复用 CSS 并渲染老板版八段结构；周度生成器只传内容数据，不重写样式。
