#!/usr/bin/env bash
set -euo pipefail

ROOT=/data1/chenwenjin
REPO="$ROOT/code/weekly_report"
RUNTIME_ENV="$ROOT/services/weekly-report/runtime.env"
LOCK_FILE="$ROOT/services/weekly-report/approve.lock"
LOG_DIR="$ROOT/log/$(date +%Y/%m/%d)"

mkdir -p "$LOG_DIR" "$(dirname "$LOCK_FILE")"
exec 9>"$LOCK_FILE"
flock -n 9 || {
  echo "another approval sync is already running" >&2
  exit 1
}

if [[ -f "$RUNTIME_ENV" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "$RUNTIME_ENV"
  set +a
fi

export PATH="$ROOT/miniconda3/envs/weekly-report/bin:/usr/bin:/bin"
cd "$REPO"

unexpected="$(
  git status --porcelain --untracked-files=no |
    awk '
      {
        path=substr($0,4)
        if (path !~ /^site\/app\/(report|archive|library|source)-data\.json$/ &&
            path !~ /^outputs\/orbitinfer\/[0-9]{4}-W[0-9]{2}\.md$/) {
          print
        }
      }
    '
)"
if [[ -n "$unexpected" ]]; then
  echo "refusing approval because the server worktree has unexpected changes:" >&2
  echo "$unexpected" >&2
  exit 1
fi

weekly-intel approve-and-export \
  --reviewer private-review-site \
  --output "$REPO/site/app/report-data.json"

cd "$REPO/site"
npm run build >>"$LOG_DIR/weekly-site-approval-build.log" 2>&1
cd "$REPO"

git add \
  site/app/report-data.json \
  site/app/archive-data.json \
  site/app/library-data.json \
  site/app/source-data.json \
  outputs/orbitinfer

iso_week="$(
  "$ROOT/miniconda3/envs/weekly-report/bin/python" -c \
    'import json; print(json.load(open("site/app/report-data.json", encoding="utf-8"))["issue"]["isoWeek"])'
)"
if ! git diff --cached --quiet; then
  git commit -m "Approve ${iso_week} weekly report"
  git push origin HEAD:main
fi

systemctl --user restart weekly-site.service
printf '{"status":"approved","isoWeek":"%s","synced":true}\n' "$iso_week"
