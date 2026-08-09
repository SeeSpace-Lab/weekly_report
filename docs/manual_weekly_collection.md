# 使用 GitHub 仓库手动完成周报采集

## 1. 适用范围

本文档说明公司成员如何从
[`SeeSpace-Lab/weekly_report`](https://github.com/SeeSpace-Lab/weekly_report)
取得正式配置，在每周一自动任务之外手动生成一份待审核周报。

这里的“手动生成”包括：

1. 同步公司仓库中的正式部门配置；
2. 从固定来源池采集最近一个完整自然周的更新；
3. 形成候选池；
4. 由 Agent 核验原始来源并生成中文精读；
5. 导入分析结果并构建本地审核页面。

手动生成必须停留在 `review` 状态。生成任务不得自动批准、提交、推送或发布周报。

## 2. GitHub 与本地环境分别负责什么

| 环节 | 执行位置 | 说明 |
|---|---|---|
| 部门范围和来源配置 | GitHub | `main` 中的配置是正式输入 |
| 配置修改和新增部门 | GitHub PR | `feature/* → develop → main` |
| 论文和公众号采集 | 本地电脑 | 依赖本地数据库、网络和 WeRSS |
| Agent 精读与写作 | 本地 Codex | 不调用仓库外的模型 API Key |
| 研究员审核 | 公开只读快照 + GitHub PR | 审核通过后合并到 `main` |
| 静态站点部署 | GitHub Actions | 只接受已经批准并进入仓库的快照 |

GitHub Actions 当前不能代替完整的本地采集和 Agent 精读。仅有 GitHub 网页访问权限，
但没有本地运行环境的成员，可以修改部门配置或重试已批准快照的部署，不能生成新一期
周报。

## 3. 权限和环境要求

### 3.1 GitHub 权限

- 已加入公司 GitHub Organization 或获得仓库访问权限；
- 能读取仓库；需要修改配置时至少拥有 Write 权限；
- 已按公司要求开启 2FA；
- 不直接向 `main` 或 `develop` 推送。

### 3.2 本地软件

- Git；
- Python 3.11 或更高版本；
- Node.js 22.13 或更高版本；
- Docker Desktop；
- Codex 桌面应用；
- 已完成公众号授权的 WeRSS 服务。

### 3.3 不得写入仓库的内容

- Token、Cookie、密码、API Key；
- `.env` 和个人账号配置；
- 内网地址、私钥和证书；
- WeRSS 登录凭据；
- 个人电脑专用的绝对路径。

凭据只能通过本地环境变量、GitHub Secrets 或公司批准的密码管理方式提供。

## 4. 首次获取仓库

在自己的工作目录执行：

```powershell
git clone https://github.com/SeeSpace-Lab/weekly_report.git
Set-Location weekly_report

python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e .

npm.cmd --prefix site ci
npm.cmd --prefix site run build
```

如果私有仓库无法克隆，先确认 GitHub 邀请、Team 或仓库权限，不要把其他成员的访问
令牌复制到自己的电脑。

## 5. 每次运行前同步正式配置

只有在工作区干净时才能同步：

```powershell
git status --short
git switch main
git pull --ff-only origin main
```

如果 `git status --short` 有输出，应停止并处理现有工作，不能使用 `reset --hard`、
覆盖文件或强制切换来清理其他人的改动。

检查可用部门：

```powershell
Get-ChildItem config\departments\*.yaml |
  Where-Object { -not $_.Name.StartsWith("_") }
```

部门配置必须满足：

```yaml
enabled: true
status: active
```

未启用部门只能维护范围和页面占位，不能生成正式周报。

## 6. 推荐方式：把提示词交给 Agent

将下面提示词复制到 Codex，并替换 `<department_id>`。当前已完整投入使用的部门示例
为 `orbitinfer`。

```text
请在当前 weekly_report 仓库中，为部门 <department_id> 手动生成研发周报待审稿。

执行要求：
1. 先检查 git status。只有工作区干净时，才能切换 main 并执行
   git pull --ff-only origin main；否则停止并报告，不得 reset、覆盖或删除改动。
2. 使用 config/departments/<department_id>.yaml 作为唯一部门范围配置。
   检查 enabled: true、status: active；未启用时停止。
3. 本次只生成“上一个完整的 Asia/Shanghai 周一至周日”，不要把当前不完整周
   或任意七天滚动窗口冒充自然周。
4. 检查 Docker Desktop 和 weekly-report-werss。容器停止时启动现有容器，
   确认 http://127.0.0.1:8001/ 可以访问，并设置
   WECHAT_FEED_BASE_URL=http://127.0.0.1:8001/feed。
5. 不配置或调用 WEEKLY_LLM_* 等外部模型 API。
6. 运行 run-weekly，并为该部门单独导出
   runs/codex/<department_id>-brief.json。
7. 阅读候选包和最新采集审计。按部门 YAML 中的使命、核心主题、邻近范围、
   排除范围、来源池、篇数和阅读时间预算完成最终选择。
8. 打开每个入选条目的论文、官方项目、会议页面、数据集或仓库等原始来源。
   公众号只能用于发现和解释，关键事实必须回到原始来源核验。不得根据标题猜测
   方法、结果或录用状态。
9. 生成 runs/codex/<department_id>-analysis.json，并按仓库的数据结构导入。
   最多 8 项，总阅读时间不超过 30 分钟；证据不足时删除条目，不降低门槛。
10. 运行 Python 测试和站点构建，然后启动该部门的本地审核页面。
11. 最终必须停留在 review 状态。不得点击审核通过，不得 commit、push、创建发布
    PR 或触发 GitHub Pages。
12. 最后报告：部门、ISO 周次、采集状态、候选数、入选数、总阅读时间、来源失败、
    质量门禁和本地审核地址。

如果部门是 orbitinfer，先完整阅读并遵守
skills/orbitinfer-weekly-survey/SKILL.md。
如果是其他部门，不得照搬 OrbitInfer 的选题范围，必须以该部门 YAML 为准。
```

## 7. 技术人员手动执行命令

以下示例使用 `orbitinfer`。运行其他部门时同时替换部门 ID、配置文件和输出文件名。

```powershell
$departmentId = "orbitinfer"
$departmentFile = "config\departments\$departmentId.yaml"
$briefFile = "runs\codex\$departmentId-brief.json"
$analysisFile = "runs\codex\$departmentId-analysis.json"

docker start weekly-report-werss
$env:WECHAT_FEED_BASE_URL = "http://127.0.0.1:8001/feed"
$env:WEEKLY_FETCH_FULLTEXT = "1"

.\.venv\Scripts\weekly-intel.exe init-db
.\.venv\Scripts\weekly-intel.exe run-weekly --days 7 `
  --department $departmentFile

.\.venv\Scripts\weekly-intel.exe export-codex-brief `
  --department $departmentFile `
  --output $briefFile
```

Agent 阅读 `$briefFile` 和最新的 `runs/*.json` 采集审计后，生成 `$analysisFile`。
随后导入并验证：

```powershell
.\.venv\Scripts\weekly-intel.exe import-codex-analysis `
  $analysisFile `
  --department $departmentFile

.\.venv\Scripts\python.exe -m unittest discover -s tests -v
npm.cmd --prefix site run build

powershell.exe -ExecutionPolicy Bypass `
  -File scripts\start_local_review.ps1 `
  -Department $departmentId
```

浏览器访问命令输出的本地地址，逐条检查题名、摘要、问题、方法、结果、证据、限制和
原始来源链接。

## 8. 时间窗口规则

标准命令在任何一天手动启动时，仍然生成上一个完整自然周：

```text
Asia/Shanghai 周一 00:00:00
至周日 23:59:59
```

例如周三手动运行，不会生成本周周一至周三的半周周报，而是重新生成上一完整周。

当前 `--iso-week` 主要用于期次标识，不能单独用来正确回填任意历史周。需要补做历史
周报时，应由维护人员先确认时间窗口能力，不得只修改 ISO 周次标签后发布。

如果目标期次已经是 `approved` 或 `published`，命令会返回
`skipped_protected`。此时必须停止，不能覆盖已批准内容。

## 9. 异常处理

### WeRSS 无法访问

检查：

```powershell
docker ps -a --filter "name=weekly-report-werss"
docker start weekly-report-werss
```

公众号授权失效时需要由获授权人员重新扫码。不得把 Cookie 或 Token 发到 Issue、
PR、Agent 对话或仓库文件中。

### OpenReview 出现验证挑战

不要循环重试挑战页面。记录该来源本次不可用，继续处理 arXiv、Crossref 和其他
来源；涉及会议录用状态时，改用会议官方录用列表或日程页面核验。

### 某个来源失败

单个来源失败时，任务可以标为 `degraded` 并继续，但最终报告必须列出失败来源。
不得用搜索摘要或其他公众号内容冒充固定来源结果。

### 候选过多

优先收紧部门 YAML 中的检索词、核心主题关键词、来源池和排除范围，不要只按规则
分数机械截断。

### 候选过少

先检查来源是否真的采集成功、时间窗口内是否有重要更新。不能为了凑满篇数降低证据
门槛。

## 10. 审核和发布边界

完成本文档流程后，周报状态应为 `review`。自动任务只推送独立开发分支并创建面向
`main` 的 PR；只有指定研究员完成远程审核并合并 PR，才视为批准。

GitHub Actions 中的 **Build remote weekly review** 会校验 PR、构建只读审核快照并
上传 Artifact。PR 正文和站点按钮提供公开审核网址。合并到 `main` 后，
**Publish approved report to GitHub Pages** 才会部署进入仓库的快照。手动点击
**Run workflow** 不会执行采集、Agent 精读或研究员审核，也不能发布 `review` 状态的内容。

手动重试部署时必须明确填写：

- `confirm`：`publish`；
- `department`：部门 ID；
- `issue`：已批准的 ISO 周次，例如 `2026-W30`。

周报 PR 的目标分支为 `main`；自动任务不得直接推送或合并 `main`。部门配置仍按
仓库既有的 `feature/* → develop → main` 规则维护。

## 11. 相关文档

- [部门新增与来源配置](department_onboarding_operations.md)
- [部门范围配置规范](department_weekly_scope_guide.md)
- [数据模型与采集合同](data_model_and_collector_contract_v0.1.md)
- [OrbitInfer Agent 工作流](../skills/orbitinfer-weekly-survey/SKILL.md)
- [Agent 分析结果结构](../skills/orbitinfer-weekly-survey/references/analysis-schema.md)
