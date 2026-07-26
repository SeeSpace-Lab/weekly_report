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
  -> 30 分钟阅读预算选稿
  -> 可选全文抓取与结构化精读
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
- 公众号只使用配置中的固定订阅池；空 Feed 与未采集到文章的账号保留在内部监控中，不展示在公开页面；
- 周报只选择本周重要论文、重要版本、框架/Benchmark/数据集及高相关公众号文章，不展示普通顶会主页动态或历史论文回看；
- 新录用且与部门高度相关的顶会论文先自动补入滚动论文库，再进入对应部门周报候选；
- 每次生成新一期时，数据库中的既有周报会同时导出到历史归档，不会被新一期覆盖；
- 精读默认使用确定性后端；配置兼容接口后生成中文题名、一句话摘要、问题、方法、结果和证据等结构化字段；
- `run-weekly` 同时生成周报、运行审计和 `site/app/report-data.json`；
- 服务器每周一北京时间 09:00 自动生成私域审核版本；
- GitHub Pages 只接受状态为 `approved` 的快照，并且只能手动触发。

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

## 私域审核与 GitHub Pages

服务器每周任务只更新私域审核站，不自动公开。研究员完成逐条审阅并将整期状态设为
`approved` 后，重新导出网页数据并把审核快照提交到仓库。随后在 GitHub Actions 中手动运行
`Publish approved report to GitHub Pages`，确认字段输入 `publish`。工作流生成纯静态快照并部署；
本仓库不会自动执行这一步。

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

## 可选配置

模型精读：

```powershell
$env:WEEKLY_LLM_API_KEY = "<key>"
$env:WEEKLY_LLM_BASE_URL = "https://api.openai.com/v1"
$env:WEEKLY_LLM_MODEL = "<model-name>"
```

对入选 arXiv 论文抓取可读 HTML 全文供内部精读：

```powershell
$env:WEEKLY_FETCH_FULLTEXT = "1"
```

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

GitHub Actions 无法访问开发机的 `127.0.0.1`。正式自动运行前，需要把 WeRSS 部署到可由 Actions 访问的受控 HTTPS 地址，将地址配置为仓库变量 `WECHAT_FEED_BASE_URL`，将访问令牌配置为仓库密钥 `WECHAT_FEED_AUTH_TOKEN`。本地 Docker 只作为开发和故障排查环境，云端服务稳定后无需为每周任务保持本机开机。

其他可选凭据：

- `OPENREVIEW_TOKEN`
- `GITHUB_TOKEN`
- `HF_TOKEN`
- `WECHAT_FEED_BASE_URL` 或各公众号配置对应的 Feed 环境变量
- `WECHAT_FEED_AUTH_TOKEN`（云端 Feed 开启鉴权时）

## 测试

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
npm.cmd --prefix site run build
```

范围、来源池、数据合同和采集约束见 [docs](docs/)。
