#!/usr/bin/env sh
set -eu

PROJECT_ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
DEFAULT_DUMP="$PROJECT_ROOT/backend/data/scenegraph_dump.sql"
DUMP_FILE=${1:-${DUMP:-$DEFAULT_DUMP}}
RESET_DB=${RESET_DB:-0}

usage() {
  cat <<'EOF'
Usage:
  make import-dump DUMP=/absolute/path/to/scenegraph_dump.sql
  RESET_DB=1 make import-dump DUMP=/absolute/path/to/scenegraph_dump.sql

Notes:
  - Supports plain SQL dumps.
  - Keep dump files local; they are ignored by git.
  - RESET_DB=1 drops and recreates the configured database before import.
EOF
}

if [ "${1:-}" = "-h" ] || [ "${1:-}" = "--help" ]; then
  usage
  exit 0
fi

if [ ! -f "$DUMP_FILE" ]; then
  echo "Dump file not found: $DUMP_FILE" >&2
  echo >&2
  usage >&2
  exit 1
fi

cd "$PROJECT_ROOT"

if [ ! -f ".env" ]; then
  cp ".env.example" ".env"
  echo "Created .env from .env.example"
fi

echo "Starting database container if needed..."
docker compose up -d db

echo "Waiting for Postgres to accept connections..."
docker compose exec -T db sh -lc '
  until pg_isready -U "$POSTGRES_USER" -d "$POSTGRES_DB" >/dev/null 2>&1; do
    sleep 1
  done
'

if [ "$RESET_DB" = "1" ]; then
  echo "RESET_DB=1: dropping and recreating database..."
  docker compose exec -T db sh -lc '
    set -eu
    psql -v ON_ERROR_STOP=1 \
      -U "$POSTGRES_USER" \
      -d postgres \
      -v db="$POSTGRES_DB" \
      -v owner="$POSTGRES_USER" <<'"'"'SQL'"'"'
SELECT pg_terminate_backend(pid)
FROM pg_stat_activity
WHERE datname = :'"'"'db'"'"' AND pid <> pg_backend_pid();
DROP DATABASE IF EXISTS :"db";
CREATE DATABASE :"db" OWNER :"owner";
SQL
  '
fi

echo "Importing SQL dump into database..."
docker compose exec -T db sh -lc '
  psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB"
' < "$DUMP_FILE"

echo "Import complete."
