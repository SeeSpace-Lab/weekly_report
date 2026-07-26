#!/usr/bin/env bash
set -euo pipefail

ROOT=/data1/chenwenjin
CODE_ROOT="$ROOT/code"
CURRENT="$CODE_ROOT/weekly_report"
STAGED="$CODE_ROOT/weekly_report-new"
BACKUP="$CODE_ROOT/weekly_report-backup-20260726"
SERVICE_DIR="$ROOT/services/weekly-report"
EXPECTED_COMMIT="${EXPECTED_COMMIT:?EXPECTED_COMMIT must be set}"

for path in "$CURRENT" "$STAGED" "$BACKUP" "$SERVICE_DIR"; do
  resolved="$(realpath -m "$path")"
  case "$resolved" in
    "$ROOT"/*) ;;
    *)
      echo "path escaped allocated server directory: $resolved" >&2
      exit 1
      ;;
  esac
done

mkdir -p "$SERVICE_DIR"
chmod 700 "$SERVICE_DIR"

if [[ ! -d "$STAGED/.git" ]]; then
  test ! -e "$STAGED"
  git clone --branch main \
    https://github.com/dccc444/weekly_report.git "$STAGED"
fi

actual_commit="$(git -C "$STAGED" rev-parse HEAD)"
if [[ "$actual_commit" != "$EXPECTED_COMMIT" ]]; then
  echo "staged commit mismatch: $actual_commit" >&2
  exit 1
fi

export PATH="$ROOT/miniconda3/envs/weekly-report/bin:/usr/bin:/bin"
mkdir -p "$STAGED/data"
python - "$CURRENT/data/weekly_intel.db" "$STAGED/data/weekly_intel.db" <<'PY'
import sqlite3
import sys

source = sqlite3.connect(f"file:{sys.argv[1]}?mode=ro", uri=True)
target = sqlite3.connect(sys.argv[2])
source.backup(target)
target.close()
source.close()
PY

npm --prefix "$STAGED/site" ci
npm --prefix "$STAGED/site" run build

if [[ ! -f "$SERVICE_DIR/runtime.env" ]]; then
  cat >"$SERVICE_DIR/runtime.env" <<'ENV'
WEEKLY_LLM_BASE_URL=https://api.openai.com/v1
WEEKLY_LLM_MODEL=gpt-5.6
WEEKLY_FETCH_FULLTEXT=1
ENV
fi
chmod 600 "$SERVICE_DIR/runtime.env"

ssh-keyscan -t ed25519 github.com >"$SERVICE_DIR/github_known_hosts"
chmod 600 "$SERVICE_DIR/github_known_hosts"
git -C "$STAGED" config user.name "weekly-report-bot"
git -C "$STAGED" config user.email "weekly-report-bot@users.noreply.github.com"
git -C "$STAGED" remote set-url origin git@github.com:dccc444/weekly_report.git
git -C "$STAGED" config core.sshCommand \
  "ssh -i $SERVICE_DIR/github_deploy_key -o IdentitiesOnly=yes -o UserKnownHostsFile=$SERVICE_DIR/github_known_hosts"
git -C "$STAGED" ls-remote origin HEAD >/dev/null

test -d "$CURRENT"
test ! -e "$BACKUP"
systemctl --user stop weekly-site.service caddy.service
mv "$CURRENT" "$BACKUP"
mv "$STAGED" "$CURRENT"
pip install -e "$CURRENT"

ln -sfn \
  "$CURRENT/deploy/server/weekly-review-api.service" \
  "$HOME/.config/systemd/user/weekly-review-api.service"
systemctl --user daemon-reload
systemctl --user enable --now weekly-review-api.service
systemctl --user restart weekly-site.service caddy.service

for _ in $(seq 1 20); do
  if curl --fail --silent \
    http://127.0.0.1:8010/api/review/status >/dev/null &&
    curl --fail --silent http://127.0.0.1:2019/config/ >/dev/null; then
    break
  fi
  sleep 1
done
curl --fail --silent http://127.0.0.1:8010/api/review/status >/dev/null
curl --fail --silent http://127.0.0.1:2019/config/ >/dev/null

LOG_DIR="$ROOT/log/$(date +%Y/%m/%d)"
LOG_FILE="$LOG_DIR/$(date +%F)_weekly-report-review-workflow.md"
mkdir -p "$LOG_DIR"
cat >"$LOG_FILE" <<EOF
# 周报审核与同步工作流部署记录

- 时间：$(date --iso-8601=seconds)
- 代码版本：$EXPECTED_COMMIT
- 新增服务：weekly-review-api.service（127.0.0.1:8010）
- 私域审核：Caddy Basic Auth 后访问审核状态和批准接口
- 公开发布：批准后仅同步 GitHub，GitHub Pages 仍需人工触发
- 大模型配置：已创建 0600 权限运行配置；API 密钥待安全写入
- 旧版本备份：$BACKUP
- 服务器公约：所有文件、环境和日志均位于 $ROOT 名下；未使用 GPU
EOF

printf 'installed=%s\nbackup=%s\nlog=%s\n' \
  "$EXPECTED_COMMIT" "$BACKUP" "$LOG_FILE"
