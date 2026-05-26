#!/usr/bin/env sh
set -eu

PROJECT_ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
DEFAULT_OUT="$PROJECT_ROOT/backend/data/scenegraph_dump_${TIMESTAMP}.sql"

OUT_FILE=${1:-${OUT:-$DEFAULT_OUT}}
FORMAT=${FORMAT:-sql}
DB_NAME=${DB_NAME:-}

usage() {
  cat <<'EOF'
Usage:
  make export-dump
  DB_NAME=scenegraph_check make export-dump
  DB_NAME=scenegraph_check OUT=/absolute/path/scenegraph_check.dump FORMAT=custom make export-dump

Options:
  DB_NAME   Source database name. Defaults to POSTGRES_DB from .env.
  OUT       Output path on host machine. Defaults to backend/data/scenegraph_dump_<timestamp>.sql
  FORMAT    sql (plain) or custom (-Fc). Default: sql
EOF
}

if [ "${1:-}" = "-h" ] || [ "${1:-}" = "--help" ]; then
  usage
  exit 0
fi

case "$FORMAT" in
  sql|custom)
    ;;
  *)
    echo "Unsupported FORMAT: $FORMAT. Use 'sql' or 'custom'." >&2
    exit 1
    ;;
esac

mkdir -p "$(dirname "$OUT_FILE")"

cd "$PROJECT_ROOT"

if [ ! -f ".env" ]; then
  cp ".env.example" ".env"
  echo "Created .env from .env.example"
fi

echo "Starting database container if needed..."
docker compose up -d db

echo "Waiting for Postgres to accept connections..."
docker compose exec -T db sh -lc '
  until pg_isready -U "$POSTGRES_USER" -d postgres >/dev/null 2>&1; do
    sleep 1
  done
'

TARGET_DB="$DB_NAME"
if [ -z "$TARGET_DB" ]; then
  TARGET_DB=$(docker compose exec -T db sh -lc 'printf "%s" "$POSTGRES_DB"')
fi

echo "Exporting database '$TARGET_DB' in format '$FORMAT'..."
if [ "$FORMAT" = "custom" ]; then
  docker compose exec -T -e TARGET_DB="$TARGET_DB" db sh -lc '
    pg_dump -U "$POSTGRES_USER" -d "$TARGET_DB" -Fc
  ' > "$OUT_FILE"
else
  docker compose exec -T -e TARGET_DB="$TARGET_DB" db sh -lc '
    pg_dump -U "$POSTGRES_USER" -d "$TARGET_DB"
  ' > "$OUT_FILE"
fi

echo "Export complete: $OUT_FILE"
