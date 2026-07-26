#!/usr/bin/env bash
set -euo pipefail

ROOT=/data1/chenwenjin
SERVICE_DIR="$ROOT/services/weekly-report"
RUNTIME_ENV="$SERVICE_DIR/runtime.env"
TEMP_ENV="$SERVICE_DIR/runtime.env.tmp"

mkdir -p "$SERVICE_DIR"
chmod 700 "$SERVICE_DIR"
read -r -s -p "请输入新的 OpenAI API Key（输入不会显示）: " api_key
printf '\n'
if [[ -z "$api_key" ]]; then
  echo "API Key 不能为空" >&2
  exit 1
fi

umask 077
{
  printf 'WEEKLY_LLM_API_KEY=%s\n' "$api_key"
  printf 'WEEKLY_LLM_BASE_URL=https://api.openai.com/v1\n'
  printf 'WEEKLY_LLM_MODEL=gpt-5.6\n'
  printf 'WEEKLY_FETCH_FULLTEXT=1\n'
} >"$TEMP_ENV"
mv "$TEMP_ENV" "$RUNTIME_ENV"
chmod 600 "$RUNTIME_ENV"
unset api_key

echo "API Key 已安全写入服务器运行环境；未写入代码仓库。"
