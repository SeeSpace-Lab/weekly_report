# 观宇芯算研发部周报

面向研究部门的自动化论文与技术情报周报流水线。当前完整服务“星载大模型推理引擎”，并为“星座智算仿真平台”保留独立范围和页面入口。系统按固定来源池采集近七天更新，统一归一化和去重，完成版本差异、部门相关性、趋势聚类、选稿、精读、审阅、Markdown 渲染及网页数据导出。

## 已实现流程

```text
arXiv / OpenReview / Crossref / GitHub / Hugging Face
公众号固定订阅池 / 顶会官方页 / 人工收件箱
  -> 原始快照与幂等入库
  -> 论文、框架、模型、数据集、综述统一身份
  -> 版本差异与综述关联
  -> 部门相关性评估与趋势聚类
  -> Python 规则评分形成最多 30 项候选包
  -> Codex Agent 完成最终筛选、原始来源核验和中文结构化精读
  -> Markdown 周报 + Web 页面数据
  -> 人工审阅、批准、发布状态
```

网页入口：

- `/`：观宇芯算研发部周报总览；
- `/departments/orbitinfer`：星载大模型推理引擎部门周报；
- `/departments/constellation-simulation`：星座智算仿真平台范围占位；
- `/archive`：按 ISO 周次浏览已经生成的历史周报；
- `/library`：近两年顶会与重要论文固定库；
- `/sources`：已经成功采集到文章的公众号及其最新内容。

主要特性：

- SQLite 保存来源、采集运行、原始记录、研究对象、版本、证据、评估、选稿和审阅记录；
- 同一来源与内容哈希幂等写入，arXiv、DOI、OpenReview 等标识用于跨来源合并；
- 单个外部来源失败或返回异常空 Feed 时保留其他结果，并在审计记录中标为 `degraded`；
- OpenReview 周报采集只查询当前会议和最近更新时间；若触发验证挑战，Codex 改用顶会官方录用/日程页面核验，不循环撞击验证页；
- 公众号只使用配置中的固定订阅池；空 Feed 与未采集到文章的账号保留在内部监控中，不展示在公开页面；
- 周报只选择本周重要论文、重要版本、框架/Benchmark/数据集及高相关公众号文章，不展示普通顶会主页动态或历史论文回看；
- 新录用且与部门高度相关的顶会论文先自动补入滚动论文库，再进入对应部门周报候选；
- 每次生成新一期时，数据库中的既有周报会同时导出到历史归档，不会被新一期覆盖；
- Python 不调用外部模型 API；Codex 本地计划任务生成中文题名、一句话摘要、问题、方法、结果和证据等结构化字段；
- `run-weekly` 同时生成部门周报、运行审计，并更新
  `site/app/department-data.json` 中对应部门的当前期次和独立归档；
- Codex 每周在本地项目中生成待审版本，并将只读审核快照随开发分支提交；
- 研究员通过公开快照和 GitHub Pull Request 审核，合并到 `main` 后由 Pages 工作流发布。

## 安装

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e .
```

网页：

```powershell
npm.cmd --prefix site ci
npm.cmd --prefix site run build
```

## GitHub 远程审核与 Pages

Codex 计划任务从最新 `origin/main` 创建独立开发分支，完成采集、精读、质量门禁和
只读站点导出后，只推送该开发分支并创建面向 `main` 的 Pull Request。PR 正文和工作流摘要
会给出公开审核网址：

```text
https://raw.githack.com/SeeSpace-Lab/weekly_report/<开发分支>/site/review/index.html
```

负责人打开该网址查看周报，点击页面中的“前往 GitHub PR 审核并合并 main”按钮，进入对应的
GitHub PR 审核流程。负责人完成审核并合并 PR 后，`Publish approved report to GitHub Pages`
会由 `main` 的推送自动触发；任务本身不会自动合并 PR 或直接推送 `main`。

本地页面仅用于开发调试，不再承担正式审核：

```powershell
powershell.exe -ExecutionPolicy Bypass -File scripts\start_local_review.ps1
```

访问 `http://127.0.0.1:3000/departments/orbitinfer/`。

指定其他部门时：

```powershell
powershell.exe -ExecutionPolicy Bypass -File `
  scripts\start_local_review.ps1 -Department <department_id>
```

## 新增部门

部门配置以公司 GitHub 仓库为唯一来源。拥有仓库 Write 权限的部门负责人可以直接
在 GitHub 网页中复制 `config/departments/_template.yaml`，创建
`config/departments/<department_id>.yaml`，然后从自己的 `feature/*` 分支向
`develop` 发起 Pull Request。PR 会自动校验全部部门配置并构建站点；负责人不需要
访问本仓库维护人的电脑，也不需要安装 Python、Node.js 或 Codex。

每个部门只维护一个 YAML，在其中填写研究使命、核心与邻近主题、排除边界、论文
检索式、重点会议、公众号、论文跟踪清单、阅读预算和审核责任。共享来源的连接端点
及 WeRSS 标识仍由 `config/sources.yaml` 统一维护。

完整字段说明和调研边界检查表见
`docs/department_weekly_scope_guide.md`；新增部门、替换公众号、调整论文数据库、
会议或期刊范围的详细步骤见 `docs/department_onboarding_operations.md`。

本地验证静态 Pages 产物：

```powershell
npm.cmd --prefix site run export:pages
```

产物位于 `site/out`，默认使用 `/weekly_report` 作为 GitHub Pages base path。

## 运行

完整周报：

```powershell
.\.venv\Scripts\weekly-intel.exe init-db
.\.venv\Scripts\weekly-intel.exe run-weekly --days 7
.\.venv\Scripts\weekly-intel.exe export-codex-brief
# Codex 按 skills/orbitinfer-weekly-survey/SKILL.md 生成 current-analysis.json
.\.venv\Scripts\weekly-intel.exe import-codex-analysis runs\codex\current-analysis.json
```

单独验证来源：

```powershell
.\.venv\Scripts\weekly-intel.exe collect-arxiv --days 7
.\.venv\Scripts\weekly-intel.exe collect-openreview --days 7
.\.venv\Scripts\weekly-intel.exe collect-crossref --days 7
.\.venv\Scripts\weekly-intel.exe collect-github --days 7
.\.venv\Scripts\weekly-intel.exe collect-huggingface --days 7
.\.venv\Scripts\weekly-intel.exe collect-wechat --days 7
.\.venv\Scripts\weekly-intel.exe collect-venues --days 7
.\.venv\Scripts\weekly-intel.exe collect-manual --days 30
```

审阅与发布：

```powershell
.\.venv\Scripts\weekly-intel.exe review-queue
.\.venv\Scripts\weekly-intel.exe review-selection <selection-id> --decision approve --reviewer <name>
.\.venv\Scripts\weekly-intel.exe approve-issue <issue-id>
.\.venv\Scripts\weekly-intel.exe publish-issue <issue-id> --page-url <url>
```

## 本地采集配置

本地 WeRSS 已按 `config/sources.yaml` 中的真实 Feed ID 对接。启动容器并完成公众号平台授权后：

```powershell
$env:WECHAT_FEED_BASE_URL = "http://127.0.0.1:8001/feed"
.\.venv\Scripts\weekly-intel.exe collect-wechat --days 7
```

若 Feed 服务经反向代理启用了令牌鉴权：

```powershell
$env:WECHAT_FEED_AUTH_TOKEN = "<token>"
```

也可在单个来源配置 `auth_token_env`、`auth_header_name` 和 `auth_scheme`。密钥仅从环境变量读取，不写入采集审计或仓库。

Codex 计划任务需要本机开机、Codex 桌面应用运行且 Docker Desktop 可用。WeRSS
只需在每周采集窗口运行；公众号登录状态失效时需要重新扫码授权。

其他可选凭据：

- `OPENREVIEW_TOKEN`
- `GITHUB_TOKEN`（可选；未配置时 GitHub Release 自动改用官方 Atom Feed，避免匿名 API 限流）
- `HF_TOKEN`
- `WECHAT_FEED_BASE_URL` 或各公众号配置对应的 Feed 环境变量
- `WECHAT_FEED_AUTH_TOKEN`（云端 Feed 开启鉴权时）

## 测试

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
npm.cmd --prefix site run build
```

范围、来源池、数据合同和采集约束见 [docs](docs/)。
