# OrbitInfer Weekly Intelligence

面向“星载大模型推理引擎”研究部门的自动化论文与技术情报周报流水线。系统按固定来源池采集近七天更新，统一归一化和去重，完成版本差异、部门相关性、趋势聚类、选稿、精读、审阅、Markdown 渲染及网页数据导出。

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

主要特性：

- SQLite 保存来源、采集运行、原始记录、研究对象、版本、证据、评估、选稿和审阅记录；
- 同一来源与内容哈希幂等写入，arXiv、DOI、OpenReview 等标识用于跨来源合并；
- 单个外部来源失败时保留其他结果，并在审计记录中标为 `degraded`；
- 公众号只使用配置中的固定订阅池；未配置 Feed 时明确返回 `blocked`；
- 精读默认使用确定性后端；配置兼容接口后使用模型输出经结构校验的 JSON；
- `run-weekly` 同时生成周报、运行审计和 `site/app/report-data.json`；
- GitHub Actions 每周一北京时间 09:00 自动运行，并验证网页构建。

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

GitHub Actions 无法访问开发机的 `127.0.0.1`。正式自动运行前，需要把 WeRSS 部署到可由 Actions 访问的受控地址，再把该地址配置为仓库变量 `WECHAT_FEED_BASE_URL`。

其他可选凭据：

- `OPENREVIEW_TOKEN`
- `GITHUB_TOKEN`
- `HF_TOKEN`
- `WECHAT_FEED_BASE_URL` 或各公众号配置对应的 Feed 环境变量

## 测试

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
npm.cmd --prefix site run build
```

范围、来源池、数据合同和采集约束见 [docs](docs/)。
