#!/usr/bin/env bash
set -euo pipefail

ROOT=/data1/chenwenjin
TODAY="$(date +%Y/%m/%d)"
LOG_DIR="$ROOT/log/$TODAY"
mkdir -p "$LOG_DIR"

export PATH="$ROOT/miniconda3/envs/weekly-report/bin:/usr/bin:/bin"
export WECHAT_FEED_BASE_URL=http://127.0.0.1:8001/feed

cd "$ROOT/code/weekly_report"
weekly-intel run-weekly --days 7 \
  >>"$LOG_DIR/weekly-report.log" 2>&1

cd site
npm run build >>"$LOG_DIR/weekly-site-build.log" 2>&1
systemctl --user restart weekly-site.service
