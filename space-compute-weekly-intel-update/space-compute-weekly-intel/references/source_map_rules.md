# 信息源规则

## 信息源地图使用目的

此信息源地图支持每周的中美太空算力产业情报工作流。它将结构化的源主数据（`source_map.csv`，唯一格式）与操作规则分离，以便分析师可以按国家、模块、优先级、扫描频率和状态过滤来源，同时保持扫描逻辑的可读性。

`source_map.csv` 当前字段：

| 字段 | 说明 |
|---|---|
| `source_id` | 稳定主键，例如 `US_POLICY_025`。 |
| `source_name` | 来源显示名。 |
| `country` | China / US / Europe / Japan / Global / Other。 |
| `region_scope` | 区域范围（China / US / Europe / China-HK 等）；Global 类来源在此列体现。 |
| `module` | Policy / Technology / Financing / Chip_AI_Compute / Market_Background；可分号多选。 |
| `source_type` | Official / Company / Database / Filing / Exchange / Industry_Media / Financial_Media / Research_Institute / Think_Tank / Other。 |
| `url` | 稳定首页或栏目页。 |
| `tier` | 单一字段，整合了来源权威性、生命周期状态和扫描动作。5 档：`S_Core` / `A_Active` / `Watch` / `Backup` / `Manual`。 |
| `notes` | 自由备注：合并历史、用例、关注点、补充说明等。 |

每周的范围是：

`太空算力 + 星载AI + 芯片 + AI基础设施 + 商业航天`

使用此信息源地图来：

- 构建每周扫描列表；
- 将来源路由到政策 / 技术 / 融资 / 芯片-AI-算力模块；
- 对来源所有权进行去重；
- 保持来源优先级与事件优先级独立；
- 在每周运行后维护 `tier` 和 `notes`。

## 来源优先级规则

- 每周扫描 `S_Core` 来源。
- 当相关模块/子模块本周活跃时扫描 `A_Active` 来源。
- 使用 `Backup` 来源进行验证、背景调查、弱信号发现或交叉分析。
- 新发现来源放入 `Watch` 状态 2-4 周或连续数周产出有效信号，再升级为 `A_Active` 或 `S_Core`。
- 不可靠/纯转载/连续失活的来源降级为 `Backup`（不要直接删除，便于历史追溯）。
- `Manual` 仅用于不在线扫描、靠手工导入文件的来源（如企查查导出）。
- 保持来源 `tier` 与事件 `event_priority` 独立：
  - `tier`：来源本身的权威性 + 扫描动作 + 生命周期状态。
  - `event_priority`：具体事件本身的重要性。
- 一个 `S_Core` 来源可能产出 `C` 级事件；一个 `Backup` 来源也可能揭示 `A` 级线索。

## 事件优先级标准

| 事件优先级 | 在简报中的使用 | 含义 |
|---|---|---|
| S | 执行摘要 / Top 10 | 重大政策转变、大型采购、战略性融资、核心竞争对手动向、重大芯片/出口管制变化，或直接影响太空算力的里程碑事件。 |
| A | 正文主体 | 具有明确行业影响的重要合同、发射、平台更新、技术验证、融资、合作伙伴关系或采购。 |
| B | 附录 / 一句话提及 | 有用的背景信息、增量产品更新、小额合同、市场背景或弱信号。 |
| C | 仅作来源记录 | 低影响、转载、纯营销、超出范围的芯片/AI报道，或未充分验证的事项。 |

## 每周高频扫描池

首先从下表生成每周扫描列表。只有当本周有相关主题或高优先级信号时，才扩展到完整信息源地图。

| 任务 | 每周 `S` 级来源 | 模块活跃时扫描的 `A` 级来源 | 验证 / 背景 `B` 级来源 | 预期输出 |
|---|---|---|---|---|
| 中国政策与法规 | gov.cn, CNSA, MIIT, NDRC, SASTIND, 新华社 | SCIO, 国家数据局, CAC, 北京/上海/海南 地方门户网站 | WIC, 地方产业园, 政策媒体 | 政策事件、部委信号、卫星互联网及算力基础设施政策。 |
| 美国政策与法规 | White House, Congress.gov, GovInfo, Federal Register, FAA AST, FCC, BIS, USSF/SSC, DARPA, SDA, NRO | NGA, DIU, NOAA Office of Space Commerce, OSTP, DARPA MTO, NASA SBIR/STTR | GAO, CSIS, CNAS, RAND, Defense News, Breaking Defense | 政策、采购、出口管制、国防太空需求及任务授权事件。 |
| 中国技术与商业航天 | CNSA, 新华社, CASC, CASIC, CGSTL, 垣信卫星 (SpaceSail), 中国星网 (China SatNet) 公开信号, 中科宇航 (CAS Space), 蓝箭航天 (LandSpace) | ADA Space, 天仪研究院 (Spacety), 航天宏图 (PIESAT), 中科星图 (GEOVIS), 银河航天 (GalaxySpace), 时空道宇 (Geespace), 微纳星空 (MinoSpace), 星河动力 (Galactic Energy), 东方空间 (Orienspace), 天兵科技 (Space Pioneer), 深蓝航天 (Deep Blue Aerospace) | CETC, CEC, 上市公司公告, 地方政府发布 | 太空算力、卫星互联网、遥感AI、发射节奏、平台及星座事件。 |
| 美国/全球技术与商业航天 | NASA, SpaceX, Rocket Lab, Planet, Maxar, BlackSky, Loft Orbital, Ubotica, Ramon.Space, AMD Space | Muon Space, Aethero, Unibap, KP Labs, Spiral Blue, Sidus/Exo-Space, ICEYE, Capella Space, Umbra, HawkEye 360 | ESA, JAXA, NOAA/NESDIS, SpaceWatch Global | 星载AI、宇航级算力、遥感AI、SAR/RF情报、任务服务及卫星平台。 |
| 融资与企业活动 | 企查查手动导出, IT桔子, 36氪, 投资界 (PEDaily), Crunchbase, SEC EDGAR, PR Newswire | 巨潮资讯 (CNInfo), 上交所 (SSE), 深交所 (SZSE), 港交所 (HKEXnews), PitchBook, CB Insights, Business Wire, GlobeNewswire, TechCrunch | Dealroom, Tracxn, 投资者博客, 地方财经媒体 | 包含金额、投资者、股权变更、合同价值、IPO/并购及一手来源的融资卡片。 |
| 芯片 / AI算力交叉领域 | BIS, 美国商务部, NIST CHIPS, CSET, CAICT, CCID, AMD Space, Microchip Space, BAE Systems Space Electronics | SemiAnalysis, TrendForce, Semiconductor Engineering, EE Times, Frontgrade, CAES, Teledyne e2v | Gartner, IDC, Omdia, ServeTheHome, 中国半导体媒体 | 出口管制、宇航级处理器/FPGA、AI算力供应链、抗辐照电子设备及算力基础设施政策。 |

## 按模块扫描顺序

### 中国政策
1. gov.cn
2. CNSA
3. MIIT
4. NDRC
5. SASTIND
6. SCIO / 国家数据局 / CAC
7. 地方门户网站：北京、上海、海南、文昌、产业园

### 美国政策
1. White House
2. Congress.gov
3. GovInfo
4. Federal Register
5. FAA AST / FCC / BIS
6. USSF / SSC
7. DARPA / SDA / NRO / NGA / DIU
8. GAO / CSIS / CNAS / RAND / 国防媒体（用于背景补充）

### 中国技术
1. CNSA / 新华社
2. CASC / CASIC / CAST / CALT / CMSA
3. 中国星网公开信号
4. CGSTL / 垣信卫星 / 银河航天 / 时空道宇 / 微纳星空
5. 中科宇航 / 蓝箭航天 / 星河动力 / 东方空间 / 天兵科技 / 深蓝航天
6. ADA Space / 天仪研究院 / 航天宏图 / 中科星图
7. CETC / CEC / 上市公司公告

### 美国技术
1. NASA / NASA SBIR-STTR / NASA TechPort
2. SpaceX / Rocket Lab / Blue Origin / AST SpaceMobile
3. DARPA / SDA / NRO / NGA / DIU / AFRL / Space RCO
4. Loft Orbital / Muon Space / Ubotica / Ramon.Space / Unibap / KP Labs / Spiral Blue / Exo-Space
5. Planet / Maxar / BlackSky / ICEYE / Capella / Umbra / HawkEye 360
6. ESA / JAXA / NOAA / SpaceWatch Global（用于国际背景）

### 融资
1. 公司新闻中心 / 投资者关系(IR)
2. SEC EDGAR / 巨潮资讯(CNInfo) / 上交所(SSE) / 深交所(SZSE) / 港交所(HKEXnews)
3. SAM.gov / USAspending / DOD 合同公告 / SpaceWERX / SBIR.gov / DSIP
4. 企查查手动导出 / IT桔子 / 天眼查
5. 36氪 / 投资界(PEDaily) / TechCrunch / Crunchbase / PitchBook / CB Insights
6. PR Newswire / Business Wire / GlobeNewswire

### 芯片 / AI算力交叉领域
1. BIS / 美国商务部 / NIST CHIPS
2. CSET / CAICT / CCID
3. AMD Space / Microchip Space / BAE Systems Space Electronics / Frontgrade / CAES
4. Renesas / Infineon / STMicroelectronics / Analog Devices / Teledyne e2v
5. SemiAnalysis / TrendForce / Semiconductor Engineering / EE Times
6. 中国半导体媒体（仅当明确涉及太空/AI算力交叉时）

## 搜索模式 (Search Patterns)

- 英文技术：`"<company or agency>" launch OR mission OR satellite OR payload OR docking OR static fire OR reuse OR constellation OR "on-orbit" OR "onboard AI"`
- 英文太空算力：`"<company>" "space compute" OR "onboard processing" OR "edge computing" OR "space-grade" OR "radiation-tolerant" OR "AI inferencing"`
- 英文遥感：`"<company or agency>" SAR OR imagery OR geospatial OR GEOINT OR hyperspectral OR "RF geolocation" OR "commercial remote sensing"`
- 英文政策：`"<agency>" commercial space OR launch OR spectrum OR remote sensing OR direct-to-device OR procurement OR export controls OR "AI chips"`
- 英文融资：`"<company>" funding OR financing OR raised OR investment OR acquisition OR merger OR contract award OR "Form D" OR "8-K" OR "S-1"`
- 中文技术：`"<公司/机构名>" 发射 OR 卫星 OR 星座 OR 商业航天 OR 遥感 OR 星上 OR 太空算力 OR 卫星互联网`
- 中文融资：`"<公司名>" 融资 OR 并购 OR 股东变更 OR 中标 OR 定增 OR IPO OR 科创债 OR 产业基金`
- 中文芯片/AI交叉：`"<公司/机构名>" 抗辐照 OR 星载计算 OR AI芯片 OR 国产GPU OR 算力基础设施 OR 出口管制`

### 补充的太空算力搜索关键词

英文：
- `"space edge computing"`
- `"onboard AI"`
- `"onboard processing"`
- `"satellite AI"`
- `"in-orbit computing"`
- `"space data center"`
- `"radiation-hardened processor"`
- `"space-grade FPGA"`
- `"satellite GPU"`
- `"remote sensing AI"`
- `"geospatial intelligence"`
- `"proliferated LEO"`
- `"defense space procurement"`

中文：
- 太空算力
- 星上计算
- 星载 AI
- 在轨计算
- 星地协同
- 卫星互联网
- 遥感 AI
- 空天信息
- 抗辐照芯片
- 星载处理器
- 商业航天
- 低轨星座
- 卫星制造
- 军工订单
- 中标
- 融资
- 股东变更

## 来源维护规则

- 在组织或出版物层级存储来源，除非必须使用特定的子页面。
- 对于公司，扫描 `News`（新闻）、`Press`（新闻稿）、`Updates`（动态）、`Missions/Launches`（任务/发射）和 `Investor Relations`（投资者关系）。
- 对于美国上市公司，在引用融资或重大合同新闻前，请核对公司IR页面及SEC EDGAR。
- 对于中国上市公司，在引用融资、重组或重大订单前，请核对上交所/深交所/巨潮资讯/港交所公告。
- 对于中国私募融资，至少交叉验证以下两个来源：企查查、IT桔子、36氪、投资界、公司新闻稿。
- 对于美国政策，按此顺序扫描：白宫 -> Congress.gov -> GovInfo -> Federal Register -> FAA/FCC/BIS/USSF -> DARPA/SDA/NRO/NGA/DIU。
- 对于太空算力相关声明，请核实事件属于硬件、飞行软件、星载AI模型、数据管道还是地面AI分析。不要将这些混为一谈。
- 对于芯片/AI报道，仅当其与太空算力、卫星通信、遥感AI、出口管制、宇航级电子设备，或针对相关瓶颈的资本配置有明确关联时才将其纳入。
- 只有当 `Watch` 来源反复产生有用信号或成为每周执行列表的一部分时，才将其提升为 `A_Active` 或 `S_Core`。
- 如果 `S_Core` 或 `A_Active` 来源变得不活跃、大部分为转载或连续 4-6 周停止产生相关信号，则降级为 `Backup`，并在 `notes` 标注 "noise" / "deprecated" / "merged into <id>"。`Noise` 不作为独立 tier 存在。

### 补充的维护规则

- `tier` 和 `event_priority` 必须分开；前者描述来源权威性和扫描动作，后者描述具体事件重要性。
- `S_Core` 来源不代表其所有事件都是 `S` 级。
- `Backup` 来源也可能产生 `A/S` 级线索，但必须回到官方、公司、交易所或数据库做验证。
- 新发现来源先进入 `Watch`，连续数周有效后再升级到 `A_Active` 或 `S_Core`。
- 每周结束后用 `notes` 记录关键变化（如来源失效、转载化、模块拓宽等）。
- 对于融资来源，企查查手工导出的 list 作为 `Manual` tier 输入，不直接替代公开新闻验证。
- 美国政策优先查官方原文，媒体报道只作为发现线索。
- 中国融资至少交叉验证企查查、IT桔子、36氪、投资界中的两个来源。

## 每周工作流

1. 阅读完整信息源地图。
2. 从每周执行表生成本周的扫描列表。
3. 首先扫描 `tier = S_Core` 来源并记录事件卡片。
4. 仅针对活跃主题扫描 `tier = A_Active` 来源：太空算力、星载AI、SAR/GEOINT、国防采购、卫星互联网、发射、融资、芯片。
5. 使用 `tier = Backup` 来源进行验证、背景补充和弱信号发现（不主动扫，只在重大事件需要核对时使用）。
6. 手动导入企查查的融资/股东变更数据。
   - 这是完整周报的必要输入；如果缺少，不生成完整融资模块和完整周报，只能在用户明确授权后生成公开信息草稿。
7. 将事件合并到一个统一事件池。**事件库字段以 `event_database_template.csv` 为唯一真源**（含 `event_id` / `date` / `published_date` / `country` / `sector` / `domain` / `entity` / `event_title` / `event_summary` / `source_name` / `source_type` / `source_url` / `source_tier` / `secondary_sources` / 三维评分 / `total_score` / `priority` / `reason_for_priority` / `include_in_report` / `implication` / `meaning_for_us` / `next_watch` / `analyst_note` / `source_discovery_flag`，共 26 列）；其他 md 文档不再单独定义字段集，需要时引用本 CSV。
8. 独立于 `source_tier` 分配 `priority = S/A/B/C`（事件优先级；不要与来源 `tier` 混用）。
9. 人工审核所有 `priority = S` 和 `priority = A` 事件。
10. 起草每周简报，分为三个部分：政策、技术、融资。
11. 将新发现的来源**写入文档章节"五、信息源地图更新建议"**（即生成建议清单，不是直接改 csv）。
12. **如需写入物理文件 `source_map.csv`**（修改受影响来源的 `tier` 与 `notes`，包括"noise" / "deprecated" / "merged into <id>" 标注），**必须先经过 SKILL.md 阶段 6 的 Source Map Write Gate JSON 流程**：打印 `pending_writes` JSON 并停止本轮回复，等用户明确回复"批准写入"后才能调用 Edit/Write 修改 csv。"运行结束后自动更新 csv" 是**错误做法**——任何 csv 物理写入都是受 gate 约束的独立动作。
