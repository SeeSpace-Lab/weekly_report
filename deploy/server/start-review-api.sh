#!/usr/bin/env bash
set -euo pipefail

ROOT=/data1/chenwenjin
RUNTIME_ENV="$ROOT/services/weekly-report/runtime.env"
export PATH="$ROOT/miniconda3/envs/weekly-report/bin:/usr/bin:/bin"
export WEEKLY_ROOT="$ROOT/code/weekly_report"

if [[ -f "$RUNTIME_ENV" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "$RUNTIME_ENV"
  set +a
fi

cd "$ROOT/code/weekly_report"
exec python -m weekly_intel.review_server
