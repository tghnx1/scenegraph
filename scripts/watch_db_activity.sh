#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
MODE="${1:-all}"
INTERVAL="${WATCH_INTERVAL:-0.5}"
CLEAR_SCREEN="${WATCH_CLEAR_SCREEN:-no}"

cd "$REPO_ROOT"

if [[ -f ".env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source ".env"
  set +a
fi

DB_ACTIVITY_URL="${DB_ACTIVITY_DATABASE_URL:-${ADMIN_DATABASE_URL:-${DATABASE_URL:-}}}"

if [[ -z "$DB_ACTIVITY_URL" ]]; then
  echo "DATABASE_URL is not set. Run make env or create .env first." >&2
  exit 1
fi

sql_all='
SELECT
  state,
  wait_event_type,
  wait_event,
  COUNT(*) AS count
FROM pg_stat_activity
WHERE datname = current_database()
  AND query NOT ILIKE $$%pg_stat_activity%$$
GROUP BY state, wait_event_type, wait_event
ORDER BY count DESC;
'

sql_updates='
SELECT
  state,
  wait_event_type,
  wait_event,
  COUNT(*) AS count
FROM pg_stat_activity
WHERE datname = current_database()
  AND query ILIKE $$%UPDATE artists%$$
  AND query NOT ILIKE $$%pg_stat_activity%$$
GROUP BY state, wait_event_type, wait_event
ORDER BY count DESC;
'

case "$MODE" in
  all)
    SQL="$sql_all"
    ;;
  updates)
    SQL="$sql_updates"
    ;;
  *)
    echo "Usage: $0 [all|updates]" >&2
    exit 2
    ;;
esac

run_query() {
  if [[ "$DB_ACTIVITY_URL" == *"@db:"* ]]; then
    docker compose exec -T db psql \
      -U "${POSTGRES_USER:-scenegraph}" \
      -d "${POSTGRES_DB:-scenegraph}" \
      -c "$SQL"
  else
    psql "$DB_ACTIVITY_URL" -c "$SQL"
  fi
}

while true; do
  if [[ "$CLEAR_SCREEN" == "yes" ]]; then
    clear
  fi
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] DB activity monitor mode=$MODE interval=${INTERVAL}s target=$(
    if [[ "$DB_ACTIVITY_URL" == *"@db:"* ]]; then
      echo "local docker db"
    elif [[ -n "${DB_ACTIVITY_DATABASE_URL:-}" ]]; then
      echo "DB_ACTIVITY_DATABASE_URL"
    elif [[ -n "${ADMIN_DATABASE_URL:-}" ]]; then
      echo "ADMIN_DATABASE_URL"
    else
      echo "DATABASE_URL"
    fi
  )"
  echo "Press Ctrl+C to stop."
  echo
  run_query
  sleep "$INTERVAL"
done
