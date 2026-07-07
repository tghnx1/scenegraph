#!/usr/bin/env sh
set -eu

PROJECT_ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
COMPOSE="${COMPOSE:-docker compose}"
LOCAL_CHROME_CDP_PORT="${LOCAL_CHROME_CDP_PORT:-9222}"
LOCAL_CHROME_CDP_URL="http://127.0.0.1:${LOCAL_CHROME_CDP_PORT}"
CONTAINER_CDP_PORT="${CONTAINER_CDP_PORT:-9222}"
CONTAINER_CDP_URL="http://127.0.0.1:${CONTAINER_CDP_PORT}"
CHROME_PROFILE_DIR="${CHROME_PROFILE_DIR:-/tmp/scenegraph-ra-chrome-profile}"

FULL_PIPELINE_MIN_DATE="${FULL_PIPELINE_MIN_DATE:-2021-01-01}"
FULL_PIPELINE_MAX_DATE="${FULL_PIPELINE_MAX_DATE:-}"
FULL_PIPELINE_ARTIFACTS_DIR="${FULL_PIPELINE_ARTIFACTS_DIR:-backend/data/import_runs}"
FULL_PIPELINE_EVENTS_JSON="${FULL_PIPELINE_EVENTS_JSON:-}"
FULL_PIPELINE_DEDUP_WITH_DB="${FULL_PIPELINE_DEDUP_WITH_DB:-yes}"
FULL_PIPELINE_SKIP_BIO="${FULL_PIPELINE_SKIP_BIO:-yes}"
FULL_PIPELINE_SKIP_TAGS="${FULL_PIPELINE_SKIP_TAGS:-no}"
FULL_PIPELINE_SKIP_EMBEDDINGS="${FULL_PIPELINE_SKIP_EMBEDDINGS:-no}"
FULL_PIPELINE_VALIDATE_ARTIST_ID="${FULL_PIPELINE_VALIDATE_ARTIST_ID:-}"
FULL_PIPELINE_KEEP_RUNS="${FULL_PIPELINE_KEEP_RUNS:-10}"

wait_for_cdp() {
  attempts="${1:-30}"
  i=1
  while [ "$i" -le "$attempts" ]; do
    if curl -fsS "${LOCAL_CHROME_CDP_URL}/json/version" >/dev/null 2>&1; then
      return 0
    fi
    sleep 1
    i=$((i + 1))
  done
  return 1
}

start_local_chrome_if_needed() {
  if curl -fsS "${LOCAL_CHROME_CDP_URL}/json/version" >/dev/null 2>&1; then
    echo "Using existing local Chrome CDP at ${LOCAL_CHROME_CDP_URL}"
    return 0
  fi

  echo "Local Chrome CDP is not running; starting Google Chrome on port ${LOCAL_CHROME_CDP_PORT}..."
  if command -v open >/dev/null 2>&1; then
    open -na "Google Chrome" --args \
      --remote-debugging-port="${LOCAL_CHROME_CDP_PORT}" \
      --user-data-dir="${CHROME_PROFILE_DIR}" \
      https://ra.co >/dev/null 2>&1 || true
  elif [ -x "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" ]; then
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
      --remote-debugging-port="${LOCAL_CHROME_CDP_PORT}" \
      --user-data-dir="${CHROME_PROFILE_DIR}" \
      https://ra.co >/dev/null 2>&1 &
  else
    cat >&2 <<ERR
Google Chrome was not found automatically.
Start it manually, then rerun make full-pipeline:

  /Applications/Google\\ Chrome.app/Contents/MacOS/Google\\ Chrome \\
    --remote-debugging-port=${LOCAL_CHROME_CDP_PORT} \\
    --user-data-dir=${CHROME_PROFILE_DIR} \\
    https://ra.co
ERR
    exit 1
  fi

  if ! wait_for_cdp 30; then
    cat >&2 <<ERR
Chrome started, but CDP did not become ready at ${LOCAL_CHROME_CDP_URL}/json/version.
Check manually with:

  curl ${LOCAL_CHROME_CDP_URL}/json/version
ERR
    exit 1
  fi

  echo "Local Chrome CDP is ready at ${LOCAL_CHROME_CDP_URL}"
}

build_pipeline_args() {
  set -- \
    backend/scripts/full_pipeline.py \
    --min-date "$FULL_PIPELINE_MIN_DATE" \
    --artifacts-dir "$FULL_PIPELINE_ARTIFACTS_DIR" \
    --keep-runs "$FULL_PIPELINE_KEEP_RUNS"

  if [ -n "$FULL_PIPELINE_MAX_DATE" ]; then
    set -- "$@" --max-date "$FULL_PIPELINE_MAX_DATE"
  fi

  if [ "$FULL_PIPELINE_SKIP_BIO" = "no" ]; then
    set -- "$@" --cdp-url "$CONTAINER_CDP_URL"
  else
    set -- "$@" --skip-bio
  fi

  if [ -n "$FULL_PIPELINE_EVENTS_JSON" ]; then
    set -- "$@" --events-json "$FULL_PIPELINE_EVENTS_JSON"
  fi
  if [ "$FULL_PIPELINE_DEDUP_WITH_DB" = "no" ]; then
    set -- "$@" --no-dedup-with-db
  fi
  if [ "$FULL_PIPELINE_SKIP_TAGS" = "yes" ]; then
    set -- "$@" --skip-tags
  fi
  if [ "$FULL_PIPELINE_SKIP_EMBEDDINGS" = "yes" ]; then
    set -- "$@" --skip-embeddings
  fi
  if [ -n "$FULL_PIPELINE_VALIDATE_ARTIST_ID" ]; then
    set -- "$@" --validate-artist-id "$FULL_PIPELINE_VALIDATE_ARTIST_ID"
  fi

  printf '%s\n' "$@"
}

cd "$PROJECT_ROOT"

pipeline_args_file="$(mktemp)"
trap 'rm -f "$pipeline_args_file"' EXIT INT TERM
build_pipeline_args > "$pipeline_args_file"

if [ "$FULL_PIPELINE_SKIP_BIO" != "no" ]; then
  # Intentional word splitting: pipeline args are generated as simple CLI tokens.
  # shellcheck disable=SC2046
  $COMPOSE --profile tools run --rm --build tools python $(cat "$pipeline_args_file")
  exit $?
fi

start_local_chrome_if_needed

echo "Starting container CDP proxy at ${CONTAINER_CDP_URL} -> host.docker.internal:${LOCAL_CHROME_CDP_PORT}"

# Intentional word splitting for the generated pipeline args; values are repo-controlled paths/dates.
# shellcheck disable=SC2046
$COMPOSE --profile tools run --rm --build \
  -e LOCAL_CHROME_CDP_PORT="$LOCAL_CHROME_CDP_PORT" \
  -e CONTAINER_CDP_PORT="$CONTAINER_CDP_PORT" \
  tools sh -lc '
set -eu

cat > /tmp/scenegraph_cdp_proxy.py <<'"'"'PY'"'"'
import os
import socket
import threading

listen_port = int(os.environ.get("CONTAINER_CDP_PORT", "9222"))
target_port = int(os.environ.get("LOCAL_CHROME_CDP_PORT", "9222"))
listen = ("127.0.0.1", listen_port)
target = ("host.docker.internal", target_port)

def close_quietly(sock):
    try:
        sock.shutdown(socket.SHUT_RDWR)
    except OSError:
        pass
    try:
        sock.close()
    except OSError:
        pass

def pipe(src, dst):
    try:
        while True:
            data = src.recv(65536)
            if not data:
                break
            dst.sendall(data)
    except OSError:
        pass
    finally:
        close_quietly(src)
        close_quietly(dst)

def handle(client):
    upstream = socket.create_connection(target)
    threading.Thread(target=pipe, args=(client, upstream), daemon=True).start()
    pipe(upstream, client)

server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
server.bind(listen)
server.listen(64)
print(
    f"CDP proxy listening on {listen[0]}:{listen[1]} -> {target[0]}:{target[1]}",
    flush=True,
)
while True:
    client, _ = server.accept()
    threading.Thread(target=handle, args=(client,), daemon=True).start()
PY

python /tmp/scenegraph_cdp_proxy.py &
proxy_pid=$!
trap "kill $proxy_pid >/dev/null 2>&1 || true" EXIT INT TERM
sleep 1
python "$@"
' _ $(cat "$pipeline_args_file")
