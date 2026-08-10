# 部门周报配置与调研范围规范

具体新增部门、替换公众号、修改论文数据库、会议和期刊范围的逐步操作见
`docs/department_onboarding_operations.md`。

## 一、配置原则

每个部门只维护一个 `config/departments/<department_id>.yaml`。共享采集端点、
公众号 WeRSS 标识和仓库连接信息继续放在 `config/sources.yaml`，部门文件只选择
需要的 `source_id` 并覆盖本部门的检索式。这样可以避免多个部门重复维护同一个
技术连接，同时保证选题范围、论文查询、公众号清单、阅读预算和审核责任集中在
一个文件中。

新增部门时，部门负责人应在公司 GitHub 网页中从
`config/departments/_template.yaml` 创建自己的
`config/departments/<department_id>.yaml` 并直接提交到 `main`。填写期间保持
`enabled: false`；完整填写后设置为 `enabled: true`，由 GitHub Actions 在 main
更新后自动验证；验证失败时必须立即修正。

## 二、范围必须回答的六个问题

1. **服务什么决策**：说明周报要支持架构选型、算法设计、工程实现、实验规划，
   还是产业判断。不能只写宽泛学科名称。
2. **核心对象是什么**：列出三至八个核心主题，每个主题给出中英文关键词、
   权重和周报板块。
3. **哪些邻近研究可以进入**：只有能够改变本部门指标、约束、方案或实验设计的
   邻近工作才纳入。
4. **哪些内容明确排除**：列出容易误入但对当前工作没有直接作用的新闻、应用、
   训练优化或泛行业材料。
5. **用什么证据判断**：明确 arXiv/OpenReview 分类与检索式、重点会议、官方
   仓库、数据集、Benchmark、公众号和人工投递来源。
6. **每周投入多少时间**：最多八项、总阅读时间不超过三十分钟；公众号是解释
   来源，关键事实仍须回到论文、项目、会场或仓库核验。

## 三、字段规范

### 标识与页面

- `department_id`：稳定的数据库标识，只能使用小写字母、数字和下划线。
- `page.slug`：URL 标识，只能使用小写字母、数字和连字符。
- `name`、`mission`、`page.description`：分别用于正式名称、研究边界和首页摘要。
- `owners`：记录内容负责人、GitHub 审核团队和写入审核记录的标签。

### 核心主题

`core_topics` 是部门相关性判断的主干。每个自定义主题必须包含：

- 唯一 `id`；
- 研究员可读的 `label`；
- `weight`，通常在 `0.6` 到 `1.0`；
- 对应周报板块 `section`；
- 足以命中论文标题和摘要的中英文 `keywords`。

一个主题应该描述可比较的技术问题，例如“在动态功率预算下进行推理调度”，
而不是“人工智能”或“系统研究”。

### 论文范围

- 在 `source_pool.overrides.arxiv` 中填写分类和检索式。
- 在 `source_pool.overrides.openreview` 中填写需要跟踪的会议。
- 用 `paper_watchlist` 填写必须持续关注的精确论文标题、Benchmark 或方法名。
- 具体论文进入周报仍须满足：本周有重要更新、证据充分、与部门任务直接相关。
- 日历更新、普通 arXiv 新稿和无验证宣传不能因为出现在跟踪清单中自动入选。

### 公众号范围

`source_pool.wechat` 只填写共享来源目录中的 `source_id`。新增公众号需要先提供：

- 公众号显示名称；
- 微信号或稳定别名；
- WeRSS 的账号 ID 或可用 Feed；
- 内容角色，例如论文解读、工程实践或趋势发现；
- 是否允许作为核心来源。

公众号只能帮助发现和解释，论文方法、指标、录用状态和开源事实必须回到原始
来源核验。

### 输出与审核

- `weekly_output.max_items` 必须为 `1-8`。
- `weekly_output.target_read_minutes` 必须为 `1-30`。
- `weekly_output.sections` 必须包含 `must_read`。
- 自定义板块必须同时配置 `section_labels`。
- `owners.content_owner` 对调研范围和内容正确性负责。
- `owners.github_team` 对公司仓库维护、校验失败处理和发布负责；不要求内容负责人拥有组织
  管理员权限。

## 四、GitHub 启用步骤

1. 在 GitHub 打开 `main` 分支的 `config/departments/_template.yaml`；
2. 复制内容并在 `config/departments` 目录通过
   **Add file → Create new file** 新建 `<department_id>.yaml`；
3. 完成配置并设置 `enabled: true`、`status: active`；
4. 选择 **Commit directly to the main branch** 并提交；
5. 等待 **Validate department configuration** 通过；
6. 检查失败时直接在 main 修正，检查通过后配置立即生效。

部门负责人不需要使用维护人的本地路径，也不需要在本地安装或运行校验工具。以下
命令仅供维护人员在需要立即试运行时使用。

运行该部门周报时显式传入：

```powershell
.\.venv\Scripts\weekly-intel.exe run-weekly --days 7 `
  --department config\departments\<department_id>.yaml

.\.venv\Scripts\weekly-intel.exe export-codex-brief `
  --department config\departments\<department_id>.yaml
```

本地审核页面：

```powershell
powershell.exe -ExecutionPolicy Bypass `
  -File scripts\start_local_review.ps1 `
  -Department <department_id>
```

地址为 `http://127.0.0.1:3000/departments/<page.slug>/`。

## 五、启用前检查表

- 部门使命能对应至少一个实际研究决策。
- 核心主题之间没有大面积重复。
- 邻近方向说明了“为什么对本部门有用”。
- 排除边界足以挡住泛新闻和弱相关内容。
- 每个自定义主题都有中英文关键词和板块。
- arXiv/OpenReview 查询不会覆盖整个宽泛学科。
- 公众号均已在 WeRSS 中验证可采集。
- 负责人、审核团队和阅读预算已确认。
- `validate-departments`、Python 测试和站点构建全部通过。
