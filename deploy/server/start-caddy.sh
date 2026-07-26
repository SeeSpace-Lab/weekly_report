#!/usr/bin/env bash
set -euo pipefail

ROOT=/data1/chenwenjin
SERVICE_DIR="$ROOT/services/caddy"

export WECHAT_FEED_AUTH_TOKEN
WECHAT_FEED_AUTH_TOKEN="$(<"$SERVICE_DIR/feed_token")"
export WEEKLY_REVIEW_PASSWORD_HASH
WEEKLY_REVIEW_PASSWORD_HASH="$(<"$SERVICE_DIR/review_password_hash")"
export XDG_DATA_HOME="$SERVICE_DIR/data"
export XDG_CONFIG_HOME="$SERVICE_DIR/config"

exec "$SERVICE_DIR/bin/caddy" run \
  --config "$ROOT/code/weekly_report/deploy/server/Caddyfile" \
  --adapter caddyfile
