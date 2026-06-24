#!/usr/bin/env sh
set -eu

export PLAYWRIGHT_BROWSERS_PATH="${PLAYWRIGHT_BROWSERS_PATH:-/ms-playwright}"

CHROME_BIN="$(python - <<'PY'
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    print(p.chromium.executable_path)
PY
)"

USER_DATA_DIR="${CHROME_USER_DATA_DIR:-/tmp/scenegraph-browser-profile}"
CDP_PORT="${CDP_PORT:-9222}"
START_URL="${CHROME_START_URL:-about:blank}"

mkdir -p "$USER_DATA_DIR"

exec "$CHROME_BIN" \
  --headless=new \
  --no-sandbox \
  --disable-dev-shm-usage \
  --disable-gpu \
  --remote-debugging-address=0.0.0.0 \
  --remote-debugging-port="$CDP_PORT" \
  --user-data-dir="$USER_DATA_DIR" \
  --no-first-run \
  --no-default-browser-check \
  "$START_URL"
