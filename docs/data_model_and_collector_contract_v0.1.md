# 周报系统数据结构与采集接口 v0.1

## 1. 目标

本设计把现有“Agent 阅读 Skill 后临时执行”的方式，改造成可定时、可恢复、可审计的流水线：

```text
Source -> Collector -> RawDocument -> Normalize/Deduplicate
       -> ResearchItem -> Evidence/Assessment
       -> WeeklySelection -> Review -> Render/Publish
```

第一版只服务“星载大模型推理引擎”部门，但所有数据结构支持后续增加其他部门。

## 2. 设计原则

1. **原始记录不可覆盖**：采集到的原始元数据和正文快照保存在 `raw_documents`。
2. **论文身份与论文版本分离**：同一论文的 arXiv、OpenReview、Camera-ready 和代码更新不能重复计数。
3. **事实与判断分离**：事实进入 `evidence_claims`，部门相关性和选稿理由进入 `department_assessments`。
4. **公众号文章不是论文主记录**：公众号文章作为 `review_article`，通过 `item_relations` 关联被解读论文。
5. **采集器不调用 LLM**：Collector 只负责可靠获取数据，LLM 分析发生在后续 Worker。
6. **所有步骤幂等**：相同来源、外部 ID 和版本重复运行不能产生重复记录。
7. **全链路可追溯**：周报中的每条判断都能回到 Research Item、Evidence 和 RawDocument。

## 3. 核心实体

### 3.1 `sources`

信息源注册表，对应现有 `source_map.csv` 的升级版。

关键字段：

- `source_id`：稳定 ID；
- `source_type`：`paper_api`、`venue`、`repository`、`model_hub`、`wechat`、`official_blog`、`manual`；
- `connector`：负责采集的 Collector 名称；
- `tier`：`S_Core`、`A_Active`、`Watch`、`Manual`；
- `config_json`：端点、账号、仓库、关键词和限速参数；
- `enabled`：是否启用。

### 3.2 `collection_runs`

记录每次采集执行：

- 采集器、来源和时间窗口；
- 开始/完成时间；
- 成功、部分成功、阻断或失败；
- 获取、创建、更新、跳过和失败数量；
- cursor、错误和重试信息。

### 3.3 `raw_documents`

Collector 的唯一标准输出落库表。

一条记录可以是：

- arXiv/OpenReview论文记录；
- 会议论文或录用事件；
- GitHub Release；
- Hugging Face模型/数据集；
- 公众号文章；
- 公司或实验室博客；
- 人工投递链接。

正文、API原始响应和解析结果都在这一层保留。

### 3.4 `research_items`

归一化后的内容主记录：

- `paper`
- `framework`
- `benchmark`
- `dataset`
- `venue_event`
- `review_article`
- `industry_update`

同一论文无论被 arXiv、OpenReview、公众号和GitHub提及多少次，只存在一个 `paper` 主记录。

### 3.5 `item_identifiers`

保存稳定标识：

- DOI；
- arXiv ID；
- OpenReview Forum ID；
- Semantic Scholar ID（后续可选）；
- GitHub `owner/repo`；
- Hugging Face Repo ID；
- URL fingerprint。

论文去重顺序：

```text
DOI
> arXiv ID
> OpenReview Forum ID
> 标准化标题 + 作者
> 人工/Agent复核
```

### 3.6 `item_versions`

记录同一 Research Item 的版本：

- arXiv v1/v2/...；
- OpenReview submission/revision；
- accepted manuscript；
- camera-ready；
- journal extension；
- framework release/tag。

版本记录包含：

- 版本时间；
-内容Hash；
- 版本说明；
- 是否存在实质变化；
- 变化摘要。

### 3.7 `item_relations`

统一保存实体关系：

- `interprets`：公众号解读论文；
- `implements`：代码实现论文；
- `extends`：后续工作扩展论文；
- `compares_with`：论文或框架比较；
- `introduces`：文章发布框架/Benchmark；
- `uses_dataset`；
- `evaluates_on`；
- `supersedes`。

### 3.8 `evidence_claims`

保存可进入周报的事实：

- claim文本；
- claim类型；
- 支撑它的原始文档和URL；
- 可选短引文；
- 证据等级；
- 抽取方式；
- 置信度；
- 是否已人工验证。

公众号中的观点与论文原文事实必须分开：

- `claim_type=fact`：必须回到一手来源；
- `claim_type=interpretation`：可以来自权威综述，但要标明作者判断。

### 3.9 `department_assessments`

每个部门对同一 Research Item 独立判断：

- 主题标签；
- 全局重要性；
- 部门相关性；
- 新颖性；
- 证据质量；
- 趋势信号；
- 推荐等级；
- 推荐理由；
- 建议周报板块；
- 预计阅读时间。

推荐等级：

- `must_read`
- `recommended`
- `scan`
- `archive`
- `exclude`

### 3.10 `weekly_issues` 与 `weekly_selections`

`weekly_issues` 保存一期周报状态：

- `draft`
- `review`
- `approved`
- `published`

`weekly_selections` 保存：

- 入选 Research Item；
- 所属板块；
- 排序；
- 内容角色；
- 入选理由；
- 摘要和部门意义；
- 预计阅读时间；
- 是否需要人工复核。

同一论文可以在“Must Read”和“近两年论文回看”中被不同期引用，但同一期只能存在一个主选择记录。

## 4. Collector接口

Python契约见：

[`src/weekly_intel/contracts.py`](../src/weekly_intel/contracts.py)

每个Collector实现：

```python
class Collector(Protocol):
    name: str

    def collect(
        self,
        source: SourceConfig,
        window: CollectionWindow,
        cursor: str | None = None,
    ) -> CollectionBatch:
        ...
```

### 4.1 输入

- `SourceConfig`：来源配置；
- `CollectionWindow`：UTC时间窗口；
- `cursor`：上次成功位置；
- `run_id`：调用方生成，用于审计；
- `limit`：单次最大获取量。

### 4.2 标准输出 `CollectedDocument`

必须包含：

- `source_id`
- `external_id`
- `document_type`
- `canonical_url`
- `title`
- `published_at`
- `discovered_at`
- `authors`
- `summary`
- `content_text`
- `content_html`
- `language`
- `identifiers`
- `metadata`
- `raw_payload`
- `content_hash`

### 4.3 Batch状态

- `ok`：完整成功；
- `partial`：部分页面或记录失败；
- `blocked`：认证、验证码或访问控制阻断；
- `error`：程序/网络错误；
- `unchanged`：没有新内容。

`blocked` 与 `error` 不能返回伪造空结果；必须写入错误和重试建议。

### 4.4 幂等键

优先：

```text
source_id + external_id
```

没有稳定外部ID时：

```text
source_id + canonical_url
```

仍无稳定URL时：

```text
source_id + sha256(normalized_title + published_at + author)
```

内容变化通过 `content_hash` 识别，生成新 `item_version`，不覆盖旧版本。

### 4.5 Cursor

不同Collector可以使用：

- 时间戳；
- arXiv `start`/分页位置；
- OpenReview修改时间；
- GitHub Release ID或更新时间；
- Hugging Face `lastModified`；
- 公众号最后文章URL/发布时间。

只有Batch状态为 `ok` 或明确可提交的 `partial` 时更新cursor。

## 5. 首批Collector

### 5.1 `ArxivCollector`

职责：

- 按分类、关键词和时间查询；
- 保存arXiv ID、版本、作者、摘要、分类、提交时间；
- 识别版本变化；
- PDF下载和全文解析由独立 `PaperContentWorker` 完成。

初始分类：

- `cs.DC`
- `cs.OS`
- `cs.PF`
- `cs.AR`
- `cs.LG`
- `cs.CL`
- `cs.CV`
- `cs.NI`

### 5.2 `OpenReviewCollector`

职责：

- 获取ICLR、NeurIPS、MLSys等OpenReview会议；
- 保存Forum ID、Invitation、submission、revision、decision和venue；
- 同时兼容API 2与历史API 1；
- 将录用状态变化写成 `venue_event`。

OpenReview API 2是当前默认版本，但部分较早会议仍使用API 1，因此不能写死单一响应结构。

### 5.3 `VenueCollector`

职责：

- 采集会议CFP、deadline、accepted papers、program、award；
- 优先使用会议官方HTML、JSON、OpenReview或proceedings；
- 会议日期和投稿时间变更生成新版本；
- “预计日期”不得自动升级为confirmed。

### 5.4 `GitHubCollector`

职责：

- 固定监控SGLang、vLLM、KTransformers、TensorRT-LLM等仓库；
- 采集Release、Tag、重要公告和仓库元数据；
- 不对全部Commit逐条生成周报事件；
- Release缺失时可按配置检查Tag或指定路径文档变化。

### 5.5 `HuggingFaceCollector`

职责：

- 按关键词、作者/组织和更新时间发现模型、数据集和Space；
- 保存Repo ID、card、tags、downloads、likes、lastModified；
- 重点识别新Benchmark、数据集和推理相关模型；
- 热度仅作排序信号，不能替代技术审阅。

### 5.6 `WechatPoolCollector`

职责：

- 只监控配置中的10个固定公众号；
- 优先使用已配置RSS/JSON订阅适配器；
- 备用方式为搜狗微信发现、已登录Chrome或人工链接；
- 不绕过验证码、登录或平台访问控制；
- 正文不可访问时返回 `partial` 或 `blocked`；
- 公众号正文只用于内部分析，不直接全文转载到周报页面。

输出的公众号文章先归一为 `review_article`，再由 `InterpretationLinkWorker` 关联论文、框架或Benchmark。

### 5.7 `ManualInboxCollector`

职责：

- 接收研究员投递的URL、PDF、Markdown或说明；
- 记录提交者、提交时间和备注；
- 不自动视为高优先级；
- 与自动采集内容使用相同的去重和审阅流程。

## 6. Collector之后的Worker

Collector与Agent分析明确分离：

1. `NormalizeWorker`
2. `IdentityResolutionWorker`
3. `VersionDiffWorker`
4. `PaperContentWorker`
5. `EvidenceExtractionWorker`
6. `InterpretationLinkWorker`
7. `DepartmentAssessmentWorker`
8. `TrendClusteringWorker`
9. `WeeklySelectionWorker`
10. `RenderWorker`

所有LLM Worker必须输出JSON，经过Schema校验后才能写入数据库。

## 7. 内部服务接口

MVP可以直接调用Python接口；需要服务化时暴露：

```text
POST /api/v1/collection-runs
GET  /api/v1/collection-runs/{run_id}
POST /api/v1/raw-documents:ingest
GET  /api/v1/review-queue
POST /api/v1/review-queue/{id}:approve
POST /api/v1/review-queue/{id}:reject
POST /api/v1/issues/{iso_week}:build
POST /api/v1/issues/{iso_week}:approve
POST /api/v1/issues/{iso_week}:publish
GET  /api/v1/items/{item_id}
GET  /api/v1/papers/{paper_id}/versions
```

写接口必须支持 `Idempotency-Key`。

## 8. MVP运行节奏

每日：

- GitHub、Hugging Face、公众号固定池；
- arXiv/OpenReview增量；
- 失败重试。

每周：

- 顶会官网与论文集；
- 全量去重和版本合并；
- 部门相关性评分；
- 趋势聚类；
- 周报候选生成；
- 人工复核与发布。

每月：

- Source Registry健康检查；
- 公众号相关率和独特信号率评估；
- 失效来源降级；
- 论文库缺口扫描。

## 9. 当前文件

- 数据库DDL：[`schemas/weekly_intel.sql`](../schemas/weekly_intel.sql)
- Collector Python契约：[`src/weekly_intel/contracts.py`](../src/weekly_intel/contracts.py)
- 部门配置：[`config/departments/orbitinfer.yaml`](../config/departments/orbitinfer.yaml)
- 来源配置：[`config/sources.yaml`](../config/sources.yaml)
- 顶会配置：[`config/venues.yaml`](../config/venues.yaml)

