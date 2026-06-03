#!/usr/bin/env sh
set -eu

PROJECT_ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
DEFAULT_DUMP="$PROJECT_ROOT/backend/data/scenegraph_dump.sql"
DUMP_FILE=${1:-${DUMP:-}}
DUMP_FORMAT=${DUMP_FORMAT:-}
RESET_DB=${RESET_DB:-0}
DB_NAME=${DB_NAME:-}
DATABASE_URL=${DATABASE_URL:-}
PG_CLIENT_IMAGE=${PG_CLIENT_IMAGE:-postgres:18}
IMPORT_DUMP_NONINTERACTIVE=${IMPORT_DUMP_NONINTERACTIVE:-0}
REMOTE_RESTORE_MODE=${REMOTE_RESTORE_MODE:-clean}
CONFIRM_IMPORT=${CONFIRM_IMPORT:-}

usage() {
  cat <<'USAGE'
Usage:
  make import-dump
  make import-dump DUMP=/absolute/path/backup.dump
  DB_NAME=scenegraph_check make import-dump DUMP=/absolute/path/backup.dump
  DATABASE_URL=postgresql://user:pass@host:5432/db?sslmode=require make import-dump DUMP=/absolute/path/backup.dump
  RESET_DB=1 DB_NAME=scenegraph_check make import-dump DUMP=/absolute/path/backup.dump
  IMPORT_DUMP_NONINTERACTIVE=1 RESET_DB=1 DB_NAME=scenegraph_check make import-dump DUMP=/absolute/path/backup.dump
  IMPORT_DUMP_NONINTERACTIVE=1 CONFIRM_IMPORT=IMPORT-REMOTE DATABASE_URL=... make import-dump DUMP=/absolute/path/backup.dump

Interactive mode:
  Running `make import-dump` in a terminal opens a restore wizard.
  Pass env vars such as DUMP, DB_NAME, DATABASE_URL, RESET_DB, or DUMP_FORMAT
  to skip specific choices.

Modes:
  - Local compose import: when DB_NAME is provided, or DATABASE_URL points to db/localhost.
  - Remote URL import: when DATABASE_URL points to a remote host.

Options:
  DUMP_FILE / DUMP        Source dump path. Supports custom (.dump) and plain SQL (.sql).
  DUMP_FORMAT             custom or sql. Defaults from file extension.
  DB_NAME                 Local compose database name. Defaults to POSTGRES_DB from compose env.
  DATABASE_URL            Target database URL for remote/cloud restore.
  RESET_DB                Local only: 1 recreates target database without asking.
  REMOTE_RESTORE_MODE     Remote custom restore mode: clean or data-only. Default: clean.
  PG_CLIENT_IMAGE         Docker image with psql/pg_restore for remote import. Default: postgres:18.
  CONFIRM_IMPORT          Required as IMPORT-REMOTE for non-interactive remote imports.

Safety:
  - Import is destructive when target objects already exist.
  - Local RESET_DB=1 drops/recreates the target database.
  - Remote custom restore uses pg_restore --clean --if-exists by default.
USAGE
}

if [ "${1:-}" = "-h" ] || [ "${1:-}" = "--help" ]; then
  usage
  exit 0
fi

cd "$PROJECT_ROOT"

EXPLICIT_DUMP_FILE=$DUMP_FILE
EXPLICIT_DATABASE_URL=$DATABASE_URL
EXPLICIT_DB_NAME=$DB_NAME
EXPLICIT_DUMP_FORMAT=$DUMP_FORMAT
EXPLICIT_RESET_DB=$RESET_DB

ENV_DATABASE_URL=
if [ -f ".env" ]; then
  ENV_DATABASE_URL=$(awk -F= '
    $1 == "DATABASE_URL" {
      value = substr($0, index($0, "=") + 1)
      gsub(/^["'\'' ]+|["'\'' ]+$/, "", value)
      print value
      exit
    }
  ' ".env")
fi

if [ -z "$DATABASE_URL" ] && [ -n "$ENV_DATABASE_URL" ]; then
  DATABASE_URL=$ENV_DATABASE_URL
fi

is_interactive=0
if [ "$IMPORT_DUMP_NONINTERACTIVE" != "1" ] && [ -t 0 ] && [ -t 1 ]; then
  is_interactive=1
fi

# Extract the host from a PostgreSQL connection URL.
database_url_host() {
  printf "%s" "$1" | sed -E 's#^[^:]+://([^:@/]+(:[^@/]*)?@)?([^:/?]+).*$#\3#'
}

# Extract the database name from a PostgreSQL connection URL.
database_url_database() {
  printf "%s" "$1" | sed -E 's#^.*//[^/]+/([^?]+).*$#\1#'
}

# Build a filesystem-safe label from a database URL.
database_url_label() {
  database_url_database "$1" | sed -E 's#[^A-Za-z0-9_.-]#_#g'
}

# Build a conservative ASCII label for local database names.
safe_database_label() {
  printf "%s" "$1" \
    | tr -cd 'A-Za-z0-9_.-' \
    | sed -E 's#^\.+##; s#\.+$##'
}

# Decide whether a database host is the local compose database.
is_local_database_host() {
  case "$1" in
    db|localhost|127.0.0.1|0.0.0.0)
      return 0
      ;;
    *)
      return 1
      ;;
  esac
}

# Return the newest dump-looking file from backend/data/backups or the legacy default.
default_dump_file() {
  latest=$(find "$PROJECT_ROOT/backend/data/backups" "$PROJECT_ROOT/backend/data" \
    -maxdepth 1 -type f \( -name '*.dump' -o -name '*.sql' \) \
    2>/dev/null | sort | tail -1 || true)
  if [ -n "$latest" ]; then
    printf "%s" "$latest"
  else
    printf "%s" "$DEFAULT_DUMP"
  fi
}

# Resolve a dump path from absolute path, current directory, backend/data/backups, or backend/data.
resolve_dump_file() {
  candidate=$1

  if [ -f "$candidate" ]; then
    printf "%s" "$candidate"
    return 0
  fi

  if [ -f "$PROJECT_ROOT/$candidate" ]; then
    printf "%s" "$PROJECT_ROOT/$candidate"
    return 0
  fi

  if [ -f "$PROJECT_ROOT/backend/data/backups/$candidate" ]; then
    printf "%s" "$PROJECT_ROOT/backend/data/backups/$candidate"
    return 0
  fi

  if [ -f "$PROJECT_ROOT/backend/data/$candidate" ]; then
    printf "%s" "$PROJECT_ROOT/backend/data/$candidate"
    return 0
  fi

  printf "%s" "$candidate"
}

# Read a value from the user's terminal.
prompt_value() {
  question=$1
  default_value=$2
  answer=
  if [ -n "$default_value" ]; then
    printf "%s [%s]: " "$question" "$default_value" > /dev/tty
  else
    printf "%s: " "$question" > /dev/tty
  fi
  IFS= read -r answer < /dev/tty || answer=
  if [ -z "$answer" ]; then
    printf "%s" "$default_value"
  else
    printf "%s" "$answer"
  fi
}

# Read a yes/no answer with a default.
prompt_yes_no() {
  question=$1
  default_value=$2
  default_label="y/N"
  if [ "$default_value" = "y" ]; then
    default_label="Y/n"
  fi

  while :; do
    printf "%s [%s]: " "$question" "$default_label" > /dev/tty
    answer=
    IFS= read -r answer < /dev/tty || answer=
    if [ -z "$answer" ]; then
      answer=$default_value
    fi
    case "$answer" in
      y|Y|yes|YES)
        return 0
        ;;
      n|N|no|NO)
        return 1
        ;;
      *)
        echo "Please answer y or n." > /dev/tty
        ;;
    esac
  done
}

# Ask the user to type an exact confirmation token for destructive imports.
prompt_confirm_token() {
  token=$1
  printf "Type %s to continue: " "$token" > /dev/tty
  answer=
  IFS= read -r answer < /dev/tty || answer=
  [ "$answer" = "$token" ]
}

# Ask for dump/source/format when the user runs make import-dump manually.
run_interactive_wizard() {
  echo "" > /dev/tty
  echo "Scenegraph database import" > /dev/tty
  echo "--------------------------" > /dev/tty

  if [ -z "$EXPLICIT_DUMP_FILE" ]; then
    DUMP_FILE=$(prompt_value "Dump file" "$(default_dump_file)")
  fi

  if [ -z "$EXPLICIT_DB_NAME" ] && [ -z "$EXPLICIT_DATABASE_URL" ]; then
    detected_label="none"
    detected_host="none"
    detected_default="1"
    if [ -n "$ENV_DATABASE_URL" ]; then
      detected_label=$(database_url_label "$ENV_DATABASE_URL")
      detected_host=$(database_url_host "$ENV_DATABASE_URL")
      if is_local_database_host "$detected_host"; then
        detected_default="2"
      else
        detected_default="1"
      fi
    fi

    echo "Detected .env DATABASE_URL: ${detected_label} @ ${detected_host}" > /dev/tty
    echo "" > /dev/tty
    echo "Choose target:" > /dev/tty
    echo "  1) .env DATABASE_URL" > /dev/tty
    echo "  2) local compose DB" > /dev/tty
    echo "  3) local compose DB by name" > /dev/tty
    echo "  4) custom DATABASE_URL" > /dev/tty
    source_choice=$(prompt_value "Target" "$detected_default")

    case "$source_choice" in
      1)
        if [ -z "$ENV_DATABASE_URL" ]; then
          echo "No DATABASE_URL found in .env." >&2
          exit 1
        fi
        DATABASE_URL=$ENV_DATABASE_URL
        DB_NAME=
        ;;
      2)
        DATABASE_URL=
        DB_NAME=
        ;;
      3)
        DATABASE_URL=
        DB_NAME=$(safe_database_label "$(prompt_value "Local DB name" "scenegraph")")
        if [ -z "$DB_NAME" ]; then
          DB_NAME=scenegraph
        fi
        ;;
      4)
        DATABASE_URL=$(prompt_value "DATABASE_URL" "")
        DB_NAME=
        if [ -z "$DATABASE_URL" ]; then
          echo "DATABASE_URL cannot be empty." >&2
          exit 1
        fi
        ;;
      *)
        echo "Invalid target choice: $source_choice" >&2
        exit 1
        ;;
    esac
  fi

  if [ -z "$EXPLICIT_DUMP_FORMAT" ]; then
    detected_format=$(detect_dump_format "$DUMP_FILE")
    echo "" > /dev/tty
    echo "Detected dump format: $detected_format" > /dev/tty
    if prompt_yes_no "Use detected format '$detected_format'?" "y"; then
      DUMP_FORMAT=$detected_format
    else
      echo "Choose format:" > /dev/tty
      echo "  1) custom (.dump / pg_restore)" > /dev/tty
      echo "  2) sql (.sql / psql)" > /dev/tty
      format_choice=$(prompt_value "Format" "1")
      case "$format_choice" in
        1|custom|dump)
          DUMP_FORMAT=custom
          ;;
        2|sql)
          DUMP_FORMAT=sql
          ;;
        *)
          echo "Invalid format choice: $format_choice" >&2
          exit 1
          ;;
      esac
    fi
  fi
}

# Infer dump format from extension.
detect_dump_format() {
  case "$1" in
    *.dump|*.backup|*.custom)
      printf "custom"
      ;;
    *)
      printf "sql"
      ;;
  esac
}

if [ "$is_interactive" = "1" ]; then
  run_interactive_wizard
fi

if [ -z "$DUMP_FILE" ]; then
  DUMP_FILE=$(default_dump_file)
fi

DUMP_FILE=$(resolve_dump_file "$DUMP_FILE")

if [ ! -f "$DUMP_FILE" ]; then
  echo "Dump file not found: $DUMP_FILE" >&2
  echo >&2
  usage >&2
  exit 1
fi

if [ -z "$DUMP_FORMAT" ]; then
  DUMP_FORMAT=$(detect_dump_format "$DUMP_FILE")
fi

case "$DUMP_FORMAT" in
  sql|custom)
    ;;
  *)
    echo "Unsupported DUMP_FORMAT: $DUMP_FORMAT. Use 'sql' or 'custom'." >&2
    exit 1
    ;;
esac

# Decide target mode after interactive choices and .env loading.
TARGET_MODE=local
TARGET_LABEL=scenegraph
if [ -n "$DB_NAME" ]; then
  TARGET_MODE=local
  DB_NAME=$(safe_database_label "$DB_NAME")
  if [ -z "$DB_NAME" ]; then
    DB_NAME=scenegraph
  fi
  TARGET_LABEL=$DB_NAME
elif [ -n "$DATABASE_URL" ]; then
  url_host=$(database_url_host "$DATABASE_URL")
  if is_local_database_host "$url_host"; then
    TARGET_MODE=local
    DB_NAME=$(safe_database_label "$(database_url_database "$DATABASE_URL")")
    if [ -z "$DB_NAME" ]; then
      DB_NAME=scenegraph
    fi
    TARGET_LABEL=$DB_NAME
  else
    TARGET_MODE=remote
    TARGET_LABEL=$(database_url_label "$DATABASE_URL")
  fi
fi

# Execute a shell command inside the local compose db container.
db_exec() {
  if [ -n "$DB_NAME" ]; then
    docker compose exec -T -e DB_NAME="$DB_NAME" db sh -lc "$1"
  else
    docker compose exec -T db sh -lc "$1"
  fi
}

# Ensure local imports can restore dumps created by superuser-owned databases.
ensure_local_compat_roles() {
  db_exec '
    if [ "$(psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d postgres -tAc "SELECT 1 FROM pg_roles WHERE rolname = '\''postgres'\''")" != "1" ]; then
      psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d postgres -c "CREATE ROLE postgres;"
    fi

    psql -U "$POSTGRES_USER" -d postgres -c "GRANT postgres TO \"$POSTGRES_USER\";" >/dev/null 2>&1 || true
  '
}

# Return 1 when a local compose database exists.
local_database_exists() {
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

# Create a local compose database.
create_local_database() {
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

# Return the Docker network used by the local compose database.
local_compose_db_network() {
  db_container_id=$(docker compose ps -q db)
  if [ -z "$db_container_id" ]; then
    echo "Database container is not running." >&2
    exit 1
  fi

  docker inspect -f '{{range $name, $_ := .NetworkSettings.Networks}}{{println $name}}{{end}}' "$db_container_id" | head -1
}

# Return an environment value from the local compose database container.
local_compose_db_env() {
  variable_name=$1
  docker compose exec -T -e VARIABLE_NAME="$variable_name" db sh -lc 'eval "printf \"%s\" \"\${$VARIABLE_NAME}\""'
}

# Drop and recreate a local compose database.
recreate_local_database() {
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

# Ask for confirmation before destructive import.
confirm_import() {
  if [ "$is_interactive" != "1" ]; then
    if [ "$TARGET_MODE" = "remote" ] && [ "$CONFIRM_IMPORT" != "IMPORT-REMOTE" ]; then
      echo "Refusing non-interactive remote import without CONFIRM_IMPORT=IMPORT-REMOTE." >&2
      exit 1
    fi
    return 0
  fi

  echo "" > /dev/tty
  echo "Import summary" > /dev/tty
  echo "  Dump:   $DUMP_FILE" > /dev/tty
  echo "  Format: $DUMP_FORMAT" > /dev/tty
  echo "  Target: $TARGET_MODE / $TARGET_LABEL" > /dev/tty
  if [ "$TARGET_MODE" = "remote" ]; then
    echo "  Remote restore mode: $REMOTE_RESTORE_MODE" > /dev/tty
    echo "" > /dev/tty
    echo "WARNING: remote import can overwrite/drop objects in AWS/RDS target DB." > /dev/tty
    prompt_confirm_token "IMPORT-REMOTE" || {
      echo "Import canceled."
      exit 0
    }
  else
    echo "  Local RESET_DB: $RESET_DB" > /dev/tty
    echo "" > /dev/tty
    if ! prompt_yes_no "Continue import?" "n"; then
      echo "Import canceled."
      exit 0
    fi
  fi

}

# Import into local docker compose Postgres.
import_into_local_compose_db() {
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

  echo "Ensuring dump compatibility roles exist..."
  ensure_local_compat_roles

  db_exists=$(local_database_exists)
  if [ "$db_exists" = "1" ]; then
    if [ "$RESET_DB" = "1" ]; then
      echo "RESET_DB=1: overwriting existing local database..."
      recreate_local_database
    else
      if [ "$is_interactive" = "1" ]; then
        if prompt_yes_no "Local database exists. Drop and recreate it before import?" "y"; then
          recreate_local_database
        else
          echo "Keeping existing local database; restore may fail on existing objects."
        fi
      else
        echo "Database already exists. Set RESET_DB=1 to overwrite it in non-interactive mode." >&2
        exit 1
      fi
    fi
  else
    echo "Database does not exist. Creating it..."
    create_local_database
  fi

  target_db=$DB_NAME
  if [ -z "$target_db" ]; then
    target_db=$(docker compose exec -T db sh -lc 'printf "%s" "$POSTGRES_DB"')
  fi

  echo "Importing $DUMP_FORMAT dump into local database '$target_db'..."
  if [ "$DUMP_FORMAT" = "custom" ]; then
    dump_dir=$(CDPATH= cd -- "$(dirname -- "$DUMP_FILE")" && pwd)
    dump_base=$(basename -- "$DUMP_FILE")
    db_network=$(local_compose_db_network)
    db_user=$(local_compose_db_env POSTGRES_USER)
    db_password=$(local_compose_db_env POSTGRES_PASSWORD)

    docker run --rm \
      --network "$db_network" \
      -e PGPASSWORD="$db_password" \
      -e TARGET_DB="$target_db" \
      -e DB_USER="$db_user" \
      -v "$dump_dir:/dump:ro" \
      "$PG_CLIENT_IMAGE" \
      sh -lc 'pg_restore --no-owner --no-privileges -f - "/dump/'"$dump_base"'" \
        | sed "/^SET transaction_timeout = 0;$/d" \
        | psql -v ON_ERROR_STOP=1 -h scenegraph-db -U "$DB_USER" -d "$TARGET_DB"'
  else
    docker compose exec -T -e TARGET_DB="$target_db" db sh -lc '
      psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$TARGET_DB"
    ' < "$DUMP_FILE"
  fi

  echo "Import complete."
}

# Import into a remote database through DATABASE_URL.
import_into_remote_database_url() {
  dump_dir=$(CDPATH= cd -- "$(dirname -- "$DUMP_FILE")" && pwd)
  dump_base=$(basename -- "$DUMP_FILE")

  echo "Importing $DUMP_FORMAT dump into remote database '$TARGET_LABEL'..."
  if [ "$DUMP_FORMAT" = "custom" ]; then
    case "$REMOTE_RESTORE_MODE" in
      clean)
        restore_mode_args="--clean --if-exists"
        ;;
      data-only)
        restore_mode_args="--data-only --disable-triggers"
        ;;
      *)
        echo "Unsupported REMOTE_RESTORE_MODE: $REMOTE_RESTORE_MODE. Use clean or data-only." >&2
        exit 1
        ;;
    esac

    docker run --rm \
      -e DATABASE_URL="$DATABASE_URL" \
      -e RESTORE_MODE_ARGS="$restore_mode_args" \
      -v "$dump_dir:/dump:ro" \
      "$PG_CLIENT_IMAGE" \
      sh -lc 'pg_restore -v --no-owner --no-privileges $RESTORE_MODE_ARGS -d "$DATABASE_URL" "/dump/'"$dump_base"'"'
  else
    docker run --rm -i \
      -e DATABASE_URL="$DATABASE_URL" \
      "$PG_CLIENT_IMAGE" \
      sh -lc 'psql -v ON_ERROR_STOP=1 "$DATABASE_URL"' < "$DUMP_FILE"
  fi

  echo "Import complete."
}

confirm_import

if [ "$TARGET_MODE" = "remote" ]; then
  import_into_remote_database_url
else
  import_into_local_compose_db
fi
