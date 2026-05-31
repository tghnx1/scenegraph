#!/usr/bin/env sh
set -eu

PROJECT_ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
DEFAULT_DUMP="$PROJECT_ROOT/backend/data/scenegraph_dump.sql"
DUMP_FILE=${1:-${DUMP:-$DEFAULT_DUMP}}
RESET_DB=${RESET_DB:-0}
DB_NAME=${DB_NAME:-}

db_exec() {
  if [ -n "$DB_NAME" ]; then
    docker compose exec -T -e DB_NAME="$DB_NAME" db sh -lc "$1"
  else
    docker compose exec -T db sh -lc "$1"
  fi
}

usage() {
  cat <<'EOF'
Usage:
  make import-dump DUMP=/absolute/path/to/scenegraph_dump.sql
  DB_NAME=scenegraph_check make import-dump DUMP=/absolute/path/to/scenegraph_dump.sql
  RESET_DB=1 make import-dump DUMP=/absolute/path/to/scenegraph_dump.sql

Notes:
  - Supports plain SQL dumps.
  - Keep dump files local; they are ignored by git.
  - By default imports into POSTGRES_DB from compose env.
  - Set DB_NAME to import into a separate database name.
  - If target database does not exist, it is created automatically.
  - If target database exists, the script asks before overwriting it.
  - RESET_DB=1 skips the prompt and overwrites the target database.
EOF
}

database_exists() {
  db_exec '
    target_db="${DB_NAME:-$POSTGRES_DB}"
    psql -v ON_ERROR_STOP=1 \
      -U "$POSTGRES_USER" \
      -d postgres \
      -v db="$target_db" \
      -tA <<'"'"'SQL'"'"'
SELECT 1 FROM pg_database WHERE datname = :'"'"'db'"'"';
SQL
  '
}

create_database() {
  db_exec '
    target_db="${DB_NAME:-$POSTGRES_DB}"
    psql -v ON_ERROR_STOP=1 \
      -U "$POSTGRES_USER" \
      -d postgres \
      -v db="$target_db" \
      -v owner="$POSTGRES_USER" <<'"'"'SQL'"'"'
CREATE DATABASE :"db" OWNER :"owner";
SQL
  '
}

recreate_database() {
  docker compose stop backend frontend nginx >/dev/null 2>&1 || true
  db_exec '
    set -eu
    target_db="${DB_NAME:-$POSTGRES_DB}"
    psql -v ON_ERROR_STOP=1 \
      -U "$POSTGRES_USER" \
      -d postgres \
      -v db="$target_db" \
      -v owner="$POSTGRES_USER" <<'"'"'SQL'"'"'
SELECT pg_terminate_backend(pid)
FROM pg_stat_activity
WHERE datname = :'"'"'db'"'"' AND pid <> pg_backend_pid();
DROP DATABASE IF EXISTS :"db";
CREATE DATABASE :"db" OWNER :"owner";
SQL
  '
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
db_exec '
  until pg_isready -U "$POSTGRES_USER" -d postgres >/dev/null 2>&1; do
    sleep 1
  done
'

DB_EXISTS=$(database_exists)

if [ "$DB_EXISTS" = "1" ]; then
  if [ "$RESET_DB" = "1" ]; then
    echo "RESET_DB=1: overwriting existing database..."
    recreate_database
  else
    printf "Database already exists. Overwrite it before import? This will delete current local data. [y/N] "
    if ! IFS= read -r ANSWER; then
      ANSWER=
      printf "\n"
    fi
    case "$ANSWER" in
      y|Y|yes|YES)
        echo "Overwriting existing database..."
        recreate_database
        ;;
      *)
        echo "Import canceled. Existing database was left unchanged."
        exit 1
        ;;
    esac
  fi
else
  echo "Database does not exist. Creating it..."
  create_database
fi

echo "Importing SQL dump into database..."
db_exec '
  target_db="${DB_NAME:-$POSTGRES_DB}"
  psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$target_db"
' < "$DUMP_FILE"

echo "Import complete."
