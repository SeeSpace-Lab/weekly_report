#!/usr/bin/env bash
set -euo pipefail

ROOT=/data1/chenwenjin
export PATH="$ROOT/miniconda3/envs/weekly-report/bin:/usr/bin:/bin"

cd "$ROOT/code/weekly_report/site"
exec ./node_modules/.bin/vinext start \
  --hostname 127.0.0.1 \
  --port 3000
