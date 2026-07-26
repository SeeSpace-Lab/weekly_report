#!/usr/bin/env bash
set -euo pipefail

ROOT=/data1/chenwenjin
export PYTHONUNBUFFERED=1
export PLAYWRIGHT_BROWSERS_PATH="$ROOT/services/we-mp-rss/playwright"
export BROWSER_TYPE=webkit
export PORT=8001
export ENABLE_JOB=True
export DEBUG=False
export LOG_FILE="$ROOT/log/we-mp-rss.log"

cd "$ROOT/code/we-mp-rss"
exec "$ROOT/miniconda3/envs/weekly-werss/bin/python" \
  main.py -job True -init True
