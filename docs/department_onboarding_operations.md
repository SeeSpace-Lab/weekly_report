# 部门周报新增与来源配置操作手册

## 1. 先说结论

部门配置以公司 GitHub 仓库
[`SeeSpace-Lab/weekly_report`](https://github.com/SeeSpace-Lab/weekly_report)
为唯一来源。其他部门负责人不需要访问维护人的本地工作区，也不需要安装 Codex、
Python 或 Node.js；拥有仓库 Write 权限后，可以直接通过 GitHub 网页创建部门 YAML
并发起 Pull Request。

在以下前提下，新增部门只需要在 GitHub 中复制并编辑一个部门 YAML：

- 使用的论文数据库、会议来源、GitHub 仓库和公众号已经登记在
  `config/sources.yaml`；
- 部门 YAML 已设置 `enabled: true`；
- YAML 能通过部门配置校验；
- 每周一 08:00 的“多部门研发周报”自动任务保持启用。

自动任务会扫描 `config/departments/*.yaml`，忽略以下划线开头的模板，只为
`enabled: true` 的部门生成周报。新增部门不需要再手写 Python、React 页面、
Pages 路由或新的站点构建脚本。

以下情况不只修改部门 YAML：

| 需求 | 是否只改部门 YAML | 还需要什么 |
|---|---:|---|
| 使用已经登记的公众号 | 是 | 在 `source_pool.wechat` 中增删 `source_id` |
| 修改 arXiv 分类或检索词 | 是 | 修改 `source_pool.overrides.arxiv` |
| 修改 OpenReview 会议 | 是 | 修改 `source_pool.overrides.openreview` |
| 修改顶会官方页面 | 是 | 修改 `source_pool.overrides.venue_official_pages` |
| 修改论文主题、排除范围、阅读预算 | 是 | 修改对应部门字段 |
| 新增一个系统从未接入的公众号 | 否 | 先配置 WeRSS，再登记到 `config/sources.yaml` |
| 新增一个系统从未接入的 GitHub 仓库 | 否 | 先在 `config/sources.yaml` 新增独立来源 |
| 严格按期刊名称建立白名单 | 暂不完全支持 | 当前 Crossref 只按检索词查询，需要增加期刊白名单过滤 |
| 新增全新的采集类型或内部数据库 | 否 | 需要实现采集器并登记共享来源 |

## 2. 在 GitHub 新增部门的标准流程

### 2.1 准备权限

部门负责人需要：

- 接受公司 GitHub Organization 或仓库邀请；
- 对 `SeeSpace-Lab/weekly_report` 至少拥有 Write 权限；
- 开启公司要求的 2FA；
- 知道本部门的 `department_id`，例如 `satellite_network`。

Write 权限足以创建功能分支和 Pull Request，不需要 Organization Owner 或仓库
Admin 权限。

### 2.2 在 GitHub 网页复制模板

1. 打开
   [`config/departments/_template.yaml`](https://github.com/SeeSpace-Lab/weekly_report/blob/develop/config/departments/_template.yaml)；
2. 点击 **Raw**，复制文件全部内容；
3. 回到
   [`config/departments`](https://github.com/SeeSpace-Lab/weekly_report/tree/develop/config/departments)；
4. 点击 **Add file → Create new file**；
5. 在当前目录下将文件名填写为 `<department_id>.yaml`，例如
   `satellite_network.yaml`；确认页面顶部最终显示的完整路径是
   `config/departments/satellite_network.yaml`；
6. 粘贴模板内容并编辑。

文件名建议与 `department_id` 一致。不要直接编辑 `_template.yaml`，因为以下划线
开头的文件会被自动任务忽略。

### 2.3 填写期间保持禁用

编辑过程中保持：

```yaml
enabled: false
status: scope_pending
```

未合并的 GitHub 分支不会被本地周报自动任务读取。保持禁用还能避免配置在尚未确认
完整时被误启用。

### 2.4 填写完整后启用

确认所有字段后改为：

```yaml
enabled: true
status: active
```

Pull Request 合入 `develop`，并随后由维护人将 `develop` 合入 `main` 后，下一次
本地自动任务同步公司仓库时会发现并运行该部门。

### 2.5 提交功能分支并创建 PR

在页面底部选择 **Create a new branch for this commit and start a pull request**，
分支名使用：

```text
feature/department-<department_id>
```

然后点击 **Propose changes**，创建目标为 `develop` 的 Pull Request，并指定仓库
维护人或 `owners.github_team` 对应团队审核。

### 2.6 等待 GitHub Actions 校验

PR 中的 **Validate department configuration** 会自动：

1. 校验字段、标识、主题、篇数、阅读时间和来源 ID；
2. 运行部门配置单元测试；
3. 根据新配置生成部门页面数据；
4. 构建站点，确认配置可以正常渲染。

检查失败时不要合并。打开失败的 Job 查看错误，在 GitHub 网页继续编辑同一分支，
修复后检查会自动重跑。部门负责人不需要在本地执行校验命令。

### 2.7 审核、合并与生效

1. 至少一名 Reviewer 审核并 Approve；
2. 所有 Actions 检查通过；
3. 维护人将功能分支合入 `develop`；
4. 按公司发布节奏，由维护人通过 PR 将 `develop` 合入 `main`；
5. 自动任务在生成周报前同步 `origin/develop`，再从该基线创建任务专属开发分支。

合入 `develop` 只代表配置通过集成审核；进入 `main` 后才成为本地自动任务使用的
正式配置。任何 GitHub Actions Secret、Token、Cookie、内网地址或账号密码都不能
写入部门 YAML、Issue 或 PR 评论。

## 3. YAML 顶层组件

推荐从 `config/departments/_template.yaml` 开始。部门文件主要由以下组件组成：

```yaml
department_id: satellite_network
name: 卫星网络与在轨计算
version: "0.1"
enabled: true
status: active
timezone: Asia/Shanghai

page: {}
owners: {}
mission: ""
core_topics: []
adjacent_topics: []
keywords: {}
paper_watchlist: []
source_pool: {}
ranking: {}
weekly_output: {}
activation_requirements: []
```

## 4. 基础标识如何填写

### `department_id`

数据库中的稳定标识。只能使用小写字母、数字和下划线，并且必须以字母开头。

正确：

```yaml
department_id: satellite_network
```

错误：

```yaml
department_id: Satellite-Network
```

部门上线后不要随意修改 `department_id`，否则历史周报会被视为另一个部门。

### `name`

页面、Markdown 周报和审核信息中的正式名称：

```yaml
name: 卫星网络与在轨计算
```

### `version`

部门范围版本。修改使命、来源或核心选题时递增：

```yaml
version: "0.2"
```

### `enabled`

- `true`：自动任务会生成该部门周报；
- `false`：只保留配置和页面占位，不采集、不选稿。

### `timezone`

决定周报使用哪个本地自然周。国内部门通常保持：

```yaml
timezone: Asia/Shanghai
```

## 5. 页面组件 `page`

示例：

```yaml
page:
  order: 3
  slug: satellite-network
  brand_mark: SN
  eyebrow: SATELLITE NETWORK WEEKLY
  headline:
    - 卫星网络
    - 在轨计算
  description: 跟踪影响星间网络、在轨任务编排和端到端时延的研究进展。
```

字段说明：

- `order`：部门在首页的顺序，数字越小越靠前；
- `slug`：页面地址，只能使用小写字母、数字和连字符；
- `brand_mark`：页面左上角的两到三个字符；
- `eyebrow`：英文辅助标题；
- `headline`：首页卡片和部门页主标题，可分成两行；
- `description`：面向读者的一句话说明。

本地维护人员预览时的页面地址为：

```text
http://127.0.0.1:3000/departments/satellite-network/
```

## 6. 负责人组件 `owners`

```yaml
owners:
  content_owner: 卫星网络研究组
  github_team: weekly-report-reviewers
  reviewer_label: satellite-network-review
```

- `content_owner`：对范围、选题和内容正确性负责；
- `github_team`：在公司 GitHub 中负责 PR 审核的团队；
- `reviewer_label`：写入本地审核记录的稳定标签。

内容负责人不需要是公司 GitHub 组织管理员。公司管理员只需一次性配置仓库权限、
Pages 和审核团队。

## 7. 研究使命 `mission`

`mission` 不能只写“关注卫星网络”或“调研人工智能”。它必须说明：

1. 部门正在做什么系统或产品；
2. 当前技术约束是什么；
3. 周报要支持什么决策；
4. 哪类研究结果能够改变部门方案。

推荐写法：

```yaml
mission: >-
  跟踪卫星网络、在轨计算和动态任务编排研究，重点服务星间链路波动、
  算力异构、能源受限和长时延环境下的架构选型、调度算法设计与仿真实验规划。
```

不推荐：

```yaml
mission: 关注卫星和人工智能的最新进展。
```

## 8. 核心主题 `core_topics`

核心主题决定候选的部门相关性、趋势聚类和周报板块。建议配置 3–8 个。

```yaml
core_topics:
  - id: dynamic_routing
    label: 动态拓扑路由
    weight: 1.0
    section: networking_and_routing
    keywords:
      - satellite network routing
      - dynamic topology routing
      - inter-satellite link
      - 星间链路路由

  - id: onboard_scheduling
    label: 在轨任务调度
    weight: 0.9
    section: onboard_compute
    keywords:
      - onboard task scheduling
      - satellite edge computing
      - 在轨任务调度
```

字段说明：

- `id`：主题稳定标识，只使用小写字母、数字和下划线；
- `label`：研究员看到的中文名称；
- `weight`：部门相关性权重，通常为 `0.6–1.0`；
- `section`：推荐条目进入的周报板块；
- `keywords`：用于论文标题、摘要和元数据匹配的中英文技术短语。

关键词应该是具体机制或问题。推荐“KV cache offloading”，不推荐“AI”。

## 9. 邻近范围 `adjacent_topics`

邻近方向不是第二套核心主题。它用于告诉 Codex：什么情况下可以纳入不完全属于
核心范围的工作。

```yaml
adjacent_topics:
  - 只有能改变星间路由约束时才纳入地面移动网络研究
  - 只有给出功耗、热约束或容错证据时才纳入边缘计算芯片研究
```

每项最好包含“只有……时才纳入”，避免范围无限扩张。

## 10. 包含与排除关键词 `keywords`

```yaml
keywords:
  include:
    - satellite network scheduling
    - onboard computing
    - inter-satellite link
    - 在轨计算
  exclude_unless_strongly_related:
    - generic terrestrial networking
    - consumer satellite internet news
    - pure remote-sensing accuracy
```

- `include`：部门候选匹配和补充分值；
- `exclude_unless_strongly_related`：命中后通常排除，除非同时有很强的核心相关性。

不要把所有宽泛术语都放进 `include`。过宽的关键词会造成候选包被普通论文淹没。

## 11. 重点论文与方法 `paper_watchlist`

```yaml
paper_watchlist:
  - title: "Exact Paper Title"
    reason: 当前系统的直接对比基线
  - query: "satellite edge computing benchmark"
    reason: 跟踪基准、数据集和重要版本
```

- `title`：适合明确论文标题；
- `query`：适合方法名、Benchmark、项目名或论文系列；
- `reason`：说明为什么要持续跟踪。

命中跟踪清单只会提高优先级，不会绕过以下条件：

- 本周必须有新论文、重要版本、录用状态或项目更新；
- 必须能打开可靠的一手来源；
- 必须与部门任务直接相关；
- 仍受最多 8 项和 30 分钟限制。

## 12. 来源池 `source_pool`

### 12.1 当前已经登记的论文与技术来源

可以直接在部门 YAML 中引用：

| `source_id` | 内容 |
|---|---|
| `arxiv` | arXiv 论文 |
| `openreview` | OpenReview 投稿与录用状态 |
| `crossref` | DOI、期刊和会议论文元数据 |
| `venue_official_pages` | 会议官方页面 |
| `github_sglang` | SGLang |
| `github_vllm` | vLLM |
| `github_ktransformers` | KTransformers |
| `github_tensorrt_llm` | TensorRT-LLM |
| `huggingface_hub` | Hugging Face 模型与数据集 |
| `manual_inbox` | 研究员人工投递 |

### 12.2 当前已经登记的公众号

| `source_id` | 公众号 |
|---|---|
| `wechat_jiqizhixin` | 机器之心 |
| `wechat_baai_hub` | 智源社区 |
| `wechat_paperweekly` | PaperWeekly |
| `wechat_ai_frontline` | AI前线 |
| `wechat_oneflow` | OneFlow |
| `wechat_qbitai` | 量子位 |
| `wechat_aiera` | 新智元 |
| `wechat_ai_tech_review` | AI科技评论 |
| `wechat_xixiaoyao` | 夕小瑶科技说 |
| `wechat_datafuntalk` | DataFunTalk |

### 12.3 部门来源池示例

```yaml
source_pool:
  papers:
    - arxiv
    - openreview
    - crossref
  venues:
    - venue_official_pages
  repositories:
    - github_vllm
  models_and_datasets:
    - huggingface_hub
  wechat:
    - wechat_paperweekly
    - wechat_ai_frontline
  manual:
    - manual_inbox
```

删除某来源时，从对应列表删除 `source_id`。系统后续不会把该来源的新内容纳入该
部门采集和评估，但不会删除数据库中的历史证据。

## 13. 更换或新增公众号

### 13.1 换成已经接入的公众号

只修改部门 YAML：

```yaml
source_pool:
  wechat:
    - wechat_jiqizhixin
    - wechat_paperweekly
```

下一次自动任务会使用新白名单。无需修改代码。

### 13.2 停用某公众号

从该部门的 `source_pool.wechat` 删除即可。若所有部门都不再使用，可以再由维护
人员将共享 `config/sources.yaml` 中的该来源设置为 `enabled: false`。

### 13.3 新增系统从未接入的公众号

需要完成一次共享技术接入：

1. 在 WeRSS 中订阅公众号并确认 Feed 能返回文章；
2. 取得稳定的账号别名和 WeRSS 账号 ID；
3. 在 `config/sources.yaml` 增加独立来源；
4. 在部门 YAML 的 `source_pool.wechat` 引用新 `source_id`；
5. 验证 WeRSS 首页和 Feed；
6. 运行部门配置校验，或等待下次自动任务校验。

共享来源示例：

```yaml
  - source_id: wechat_example_account
    name: 示例公众号
    source_type: wechat
    connector: WechatPoolCollector
    tier: A_Active
    provider: we-mp-rss
    account_alias: exampleAlias
    account_id: MP_WXS_0000000000
    feed_url_env: WECHAT_FEED_EXAMPLE_ACCOUNT
    content_role: paper_interpretation
    access_mode: local_subscription_ready
    fallbacks: [sogou_search, chrome, manual_url]
    schedule: daily
```

注意：

- `source_id` 必须全局唯一；
- `account_id` 必须来自实际 WeRSS 订阅；
- 不得复制另一个公众号的账号 ID；
- 没有可用 Feed 时必须报告阻塞，不能伪造公众号结果；
- 公众号内容只能作解释，关键事实仍需核验论文或官方项目。

## 14. 更换论文数据库、会议或“刊物”

“刊物”需要区分论文数据库、会议和具体期刊。

### 14.1 arXiv 分类和检索式

```yaml
source_pool:
  papers:
    - arxiv
  overrides:
    arxiv:
      categories: [cs.NI, cs.DC, cs.OS]
      search_terms:
        - satellite network routing
        - onboard task scheduling
        - space edge computing
```

`categories` 和 `search_terms` 都会实际用于下一次采集。

更换范围时直接替换列表。不要只增加新词而忘记删除已经不需要的旧词。

### 14.2 OpenReview 会议

```yaml
source_pool:
  papers:
    - openreview
  overrides:
    openreview:
      venues:
        - venue_id: ICLR.cc/2026/Conference
          venue: ICLR
          year: 2026
        - venue_id: NeurIPS.cc/2026/Conference
          venue: NeurIPS
          year: 2026
      page_size: 100
      max_pages: 3
```

每年应更新 `venue_id` 和 `year`。OpenReview 出现挑战页面时，自动任务不会循环
重试，而会使用其他论文来源和官方会议页面继续。

### 14.3 会议官方页面

```yaml
source_pool:
  venues:
    - venue_official_pages
  overrides:
    venue_official_pages:
      pages:
        - id: sigcomm-2027
          name: SIGCOMM 2027
          category: networking
          url: https://conferences.sigcomm.org/sigcomm/2027/
        - id: nsdi-2027
          name: NSDI 2027
          category: systems_networking
          url: https://www.usenix.org/conference/nsdi27
```

部门覆盖项会替换该部门使用的默认会议页面列表。官方日历更新只作为证据，不会
自动进入部门周报正文。

### 14.4 Crossref 与具体期刊

当前 Crossref 采集支持部门专属检索词：

```yaml
source_pool:
  papers:
    - crossref
  overrides:
    crossref:
      search_terms:
        - satellite edge computing IEEE TCC
        - onboard computing IEEE TPDS
      rows_per_query: 50
```

当前限制：系统会保存 Crossref 返回的 `container-title`，但尚未执行严格的期刊
名称白名单过滤。因此：

- 将期刊名写入检索词可以缩小范围，但不能保证返回结果全部来自该期刊；
- 如果部门要求“只允许指定期刊”，需要新增显式期刊白名单和过滤逻辑；
- 在该能力完成前，Codex 最终筛选必须核验 DOI 页面、出版机构和期刊名称。

### 14.5 删除某类论文来源

如果部门不需要 Crossref：

```yaml
source_pool:
  papers:
    - arxiv
    - openreview
```

不要在 `source_pool.overrides` 中保留已经从来源池删除的配置，避免误导维护人员。

## 15. 新增或更换 GitHub 仓库

使用已经登记的仓库时，只改部门 YAML：

```yaml
source_pool:
  repositories:
    - github_vllm
    - github_sglang
```

新增未登记仓库时，在 `config/sources.yaml` 创建新的全局来源：

```yaml
  - source_id: github_example_runtime
    name: Example Runtime GitHub
    source_type: repository
    connector: GitHubCollector
    tier: A_Active
    homepage_url: https://github.com/example/runtime
    repository: example/runtime
    token_env: GITHUB_TOKEN
    collect: [releases, tags, repository_metadata]
    schedule: daily
```

然后在部门 YAML 中引用 `github_example_runtime`。不要复用
`github_vllm` 等已有 `source_id` 去指向另一个仓库。

## 16. 排名组件 `ranking`

示例：

```yaml
ranking:
  global_importance:
    venue_or_review_status: 0.20
    system_novelty: 0.20
    evidence_and_reproducibility: 0.20
    trend_signal: 0.15
    artifact_value: 0.15
    version_significance: 0.10
```

这些权重用于规则候选，不代表最终编辑决定。最终入选仍由 Codex 阅读原始来源后
完成。通常不要频繁调整权重；优先修正使命、主题、关键词和来源范围。

## 17. 输出组件 `weekly_output`

```yaml
weekly_output:
  target_read_minutes: 30
  max_items: 8
  max_wechat_items: 3
  wechat_candidate_reserve: 8
  must_read_min: 3
  must_read_max: 5
  deep_read_min: 8
  deep_read_max: 12
  quick_scan_min: 10
  quick_scan_max: 20
  sections:
    - weekly_trends
    - must_read
    - networking_and_routing
    - onboard_compute
    - frameworks_benchmarks_datasets
    - department_relevance
  section_labels:
    must_read: 本周必读
    networking_and_routing: 网络与路由
    onboard_compute: 在轨计算与调度
    frameworks_benchmarks_datasets: 框架、Benchmark 与数据集
    department_relevance: 部门专项意义
```

硬性限制：

- `max_items` 必须为 `1–8`；
- `target_read_minutes` 必须为 `1–30`；
- `sections` 必须包含 `must_read`；
- `core_topics[*].section` 必须出现在 `sections`；
- 每个自定义板块都应有 `section_labels` 中文名称。

`deep_read_min/max` 和 `quick_scan_min/max` 是单项建议阅读时长，不是整期总时长。

## 18. 启用条件 `activation_requirements`

```yaml
activation_requirements:
  - 部门使命和近期研究决策已确认
  - 核心主题、邻近主题和排除边界已确认
  - 论文来源、会议、检索式和公众号已确认
  - 内容负责人和 GitHub 审核团队已确认
```

这是部门负责人启用前的检查表。字段本身不会代替配置校验。

## 19. 自动任务如何处理部门

每周一 08:00，“多部门研发周报”会：

1. 同步公司仓库 `origin/develop`，并从该基线创建任务专属开发分支；
2. 校验所有部门 YAML；
3. 同步部门目录和页面；
4. 读取全部 `enabled: true` 的部门；
5. 按部门来源池独立采集和形成候选；
6. 按部门使命、主题和排除范围独立筛选；
7. 为每个部门生成独立候选包和分析文件；
8. 导入中文精读并保持状态为 `review`；
9. 统一运行 Python 测试、站点构建和 Pages 静态导出；
10. 提交到任务专属开发分支，只推送该分支并向 `develop` 创建 Draft PR；
11. 由研究员在 GitHub PR 和只读站点 Artifact 中远程审核，不自动批准或发布。

如果本地存在未提交改动，自动任务必须停止并报告，不能通过 reset、覆盖文件或强制
合并来获取远端配置。这样 GitHub 上已进入 `main` 的部门配置才是下一次生成任务的
输入，同时不会破坏尚未审核的本地周报。

如果某部门本期已经 `approved` 或 `published`，自动任务会保护该期内容并跳过，
不会覆盖已批准选择。

## 20. 本地立即试运行

不想等待自动任务时，可以手动运行一个部门：

```powershell
$departmentFile = "config\departments\satellite_network.yaml"

.\.venv\Scripts\weekly-intel.exe run-weekly --days 7 `
  --department $departmentFile

.\.venv\Scripts\weekly-intel.exe export-codex-brief `
  --department $departmentFile `
  --output runs\codex\satellite_network-brief.json
```

如需开发调试，可启动该部门只读页面；正式审核仍在 GitHub PR：

```powershell
powershell.exe -ExecutionPolicy Bypass `
  -File scripts\start_local_review.ps1 `
  -Department satellite_network
```

## 21. 常见问题

### 新建 YAML 后首页没有部门

检查：

- 文件是否仍以下划线开头；
- YAML 是否位于 `config/departments`；
- 是否运行过 `sync-departments`，或是否已经等到自动任务；
- `page.slug` 是否有效且未与其他部门重复。

### 部门只显示“范围待确认”

检查：

```yaml
enabled: true
status: active
```

同时确认核心主题、关键词、来源池和输出板块已填写。

### 自动任务没有生成新部门

检查：

- `enabled` 是否为布尔值 `true`，而不是字符串 `"true"`；
- 文件名是否以下划线开头；
- `validate-departments` 是否通过；
- 自动任务是否处于 ACTIVE；
- 该周是否已经处于 `approved` 或 `published`。

### 公众号没有结果

检查：

- 公众号是否在部门 `source_pool.wechat`；
- `source_id` 是否存在于 `config/sources.yaml`；
- Docker Desktop 和 `weekly-report-werss` 是否运行；
- `http://127.0.0.1:8001/` 是否返回成功；
- WeRSS 登录授权是否失效；
- 该公众号本周是否确实有文章。

不得用搜索结果或其他公众号文章冒充缺失的固定订阅结果。

### 候选太多且不相关

依次收紧：

1. `source_pool.overrides.*.search_terms`；
2. arXiv 分类或 OpenReview 会场；
3. `core_topics[*].keywords`；
4. `keywords.include`；
5. `exclude_unless_strongly_related`；
6. 删除不需要的公众号、仓库或论文数据库。

### 候选太少

依次检查：

1. 来源是否采集成功；
2. 检索词是否过于精确；
3. 中英文关键词是否齐全；
4. 邻近方向是否确实允许纳入；
5. `paper_watchlist` 是否覆盖当前项目的明确基线；
6. 时间窗口内是否真的有重要更新。

不能为了凑数降低证据门槛。

## 22. 修改完成后的检查表

- [ ] `department_id` 和 `page.slug` 唯一且格式正确；
- [ ] `mission` 对应明确的研究或工程决策；
- [ ] 配置了 3–8 个核心主题；
- [ ] 每个自定义主题都有中英文关键词和板块；
- [ ] 邻近方向写明了纳入条件；
- [ ] 排除项能够挡住泛新闻和弱相关研究；
- [ ] arXiv/OpenReview/Crossref 查询范围已确认；
- [ ] 重点会议和官方页面已确认；
- [ ] 公众号均为实际需要且已经接入 WeRSS；
- [ ] 新 GitHub 仓库使用独立 `source_id`；
- [ ] `max_items <= 8`；
- [ ] `target_read_minutes <= 30`；
- [ ] 内容负责人和 GitHub 审核团队已填写；
- [ ] 完成后设置 `enabled: true`、`status: active`；
- [ ] GitHub PR 的 **Validate department configuration** 已通过；
- [ ] 周报最终由研究员在面向 `develop` 的 GitHub PR 中远程审核。

## 23. 相关文件

- 部门模板：`config/departments/_template.yaml`
- OrbitInfer 示例：`config/departments/orbitinfer.yaml`
- 部门范围规范：`docs/department_weekly_scope_guide.md`
- 共享来源目录：`config/sources.yaml`
- 固定论文库：`config/paper_library.yaml`
- 会议目录：`config/venues.yaml`
- 自动生成的部门站点数据：`site/app/department-data.json`

不要手工编辑 `site/app/department-data.json`。它由部门同步和周报导出流程自动生成。
