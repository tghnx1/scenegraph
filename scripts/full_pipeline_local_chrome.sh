#!/usr/bin/env sh
set -eu

PROJECT_ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
COMPOSE="${COMPOSE:-docker compose}"
LOCAL_CHROME_CDP_PORT="${LOCAL_CHROME_CDP_PORT:-9222}"
LOCAL_CHROME_CDP_URL="http://127.0.0.1:${LOCAL_CHROME_CDP_PORT}"
CONTAINER_CDP_PORT="${CONTAINER_CDP_PORT:-9222}"
CONTAINER_CDP_URL="http://127.0.0.1:${CONTAINER_CDP_PORT}"

FULL_PIPELINE_MIN_DATE="${FULL_PIPELINE_MIN_DATE:-2021-01-01}"
FULL_PIPELINE_MAX_DATE="${FULL_PIPELINE_MAX_DATE:-}"
FULL_PIPELINE_ARTIFACTS_DIR="${FULL_PIPELINE_ARTIFACTS_DIR:-backend/data/import_runs}"
FULL_PIPELINE_EVENTS_JSON="${FULL_PIPELINE_EVENTS_JSON:-}"
FULL_PIPELINE_DEDUP_WITH_DB="${FULL_PIPELINE_DEDUP_WITH_DB:-yes}"
FULL_PIPELINE_SKIP_BIO="${FULL_PIPELINE_SKIP_BIO:-no}"
FULL_PIPELINE_SKIP_TAGS="${FULL_PIPELINE_SKIP_TAGS:-no}"
FULL_PIPELINE_SKIP_EMBEDDINGS="${FULL_PIPELINE_SKIP_EMBEDDINGS:-no}"
FULL_PIPELINE_VALIDATE_ARTIST_ID="${FULL_PIPELINE_VALIDATE_ARTIST_ID:-}"

if ! curl -fsS "${LOCAL_CHROME_CDP_URL}/json/version" >/dev/null 2>&1; then
  cat >&2 <<EOF
Local Chrome CDP is not ready at ${LOCAL_CHROME_CDP_URL}/json/version.

Start a real local Chrome session first:

  /Applications/Google\\ Chrome.app/Contents/MacOS/Google\\ Chrome \\
    --remote-debugging-port=${LOCAL_CHROME_CDP_PORT} \\
    --user-data-dir=/tmp/scenegraph-ra-chrome-profile \\
    https://ra.co

Then verify:

  curl ${LOCAL_CHROME_CDP_URL}/json/version
EOF
  exit 1
fi

set -- \
  backend/scripts/full_pipeline.py \
  --min-date "$FULL_PIPELINE_MIN_DATE" \
  --max-date "$FULL_PIPELINE_MAX_DATE" \
  --artifacts-dir "$FULL_PIPELINE_ARTIFACTS_DIR" \
  --cdp-url "$CONTAINER_CDP_URL"

if [ -n "$FULL_PIPELINE_EVENTS_JSON" ]; then
  set -- "$@" --events-json "$FULL_PIPELINE_EVENTS_JSON"
fi
if [ "$FULL_PIPELINE_DEDUP_WITH_DB" = "no" ]; then
  set -- "$@" --no-dedup-with-db
fi
if [ "$FULL_PIPELINE_SKIP_BIO" = "yes" ]; then
  set -- "$@" --skip-bio
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

cd "$PROJECT_ROOT"

echo "Using local Chrome CDP at ${LOCAL_CHROME_CDP_URL}"
echo "Starting container CDP proxy at ${CONTAINER_CDP_URL} -> host.docker.internal:${LOCAL_CHROME_CDP_PORT}"

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
' _ "$@"
