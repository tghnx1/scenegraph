#!/usr/bin/env sh
set -eu

PROJECT_ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
FORMAT=${FORMAT:-}
DB_NAME=${DB_NAME:-}
DATABASE_URL=${DATABASE_URL:-}
OUT=${OUT:-}
PG_DUMP_IMAGE=${PG_DUMP_IMAGE:-postgres:18}
EXCLUDE_TABLES=${EXCLUDE_TABLES:-}
EXPORT_DUMP_NONINTERACTIVE=${EXPORT_DUMP_NONINTERACTIVE:-0}

usage() {
  cat <<'USAGE'
Usage:
  make export-dump
  DB_NAME=scenegraph_check make export-dump
  DATABASE_URL=postgresql://user:pass@host:5432/db?sslmode=require make export-dump
  FORMAT=custom make export-dump
  OUT=/absolute/path/backup.dump FORMAT=custom make export-dump
  EXCLUDE_TABLES='_emb_snapshot_*' FORMAT=custom make export-dump
  EXPORT_DUMP_NONINTERACTIVE=1 FORMAT=custom make export-dump

Interactive mode:
  Running `make export-dump` in a terminal opens a small backup wizard.
  Pass env vars such as DB_NAME, DATABASE_URL, FORMAT, OUT, or EXCLUDE_TABLES
  to skip specific choices.

Modes:
  - URL export: when DATABASE_URL points to a remote host.
  - Local compose export: when DB_NAME is provided, or DATABASE_URL points to db/localhost.

Options:
  DB_NAME         Local compose database name. Defaults to POSTGRES_DB from compose env.
  DATABASE_URL    Source database URL for remote/cloud export.
  OUT             Output path on host machine.
  FORMAT          sql (plain) or custom (-Fc). Default: custom in interactive mode, sql otherwise.
  PG_DUMP_IMAGE   Docker image with pg_dump for URL export. Default: postgres:18.
  EXCLUDE_TABLES  Optional comma-separated pg_dump --exclude-table patterns.

Notes:
  - URL export never starts or uses the local compose db service.
  - Local compose export preserves the previous make export-dump behavior.
  - Dump files are ignored by git when written under backend/data/backups/.
USAGE
}

if [ "${1:-}" = "-h" ] || [ "${1:-}" = "--help" ]; then
  usage
  exit 0
fi

cd "$PROJECT_ROOT"

EXPLICIT_DATABASE_URL=$DATABASE_URL
EXPLICIT_DB_NAME=$DB_NAME
EXPLICIT_FORMAT=$FORMAT
EXPLICIT_OUT=$OUT
EXPLICIT_EXCLUDE_TABLES=$EXCLUDE_TABLES

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
if [ "$EXPORT_DUMP_NONINTERACTIVE" != "1" ] && [ -t 0 ] && [ -t 1 ]; then
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

# Build a conservative ASCII label for database names and output filenames.
safe_database_label() {
  printf "%s" "$1" \
    | tr -cd 'A-Za-z0-9_.-' \
    | sed -E 's#^\\.+##; s#\\.+$##'
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

# Read a value from the user's terminal without exposing secrets from existing env vars.
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

# Ask for source/format/output when the user runs make export-dump manually.
run_interactive_wizard() {
  echo "" > /dev/tty
  echo "Scenegraph database export" > /dev/tty
  echo "--------------------------" > /dev/tty

  if [ -z "$EXPLICIT_DB_NAME" ] && [ -z "$EXPLICIT_DATABASE_URL" ]; then
    detected_label="none"
    detected_host="none"
    detected_default="2"
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
    echo "Choose source:" > /dev/tty
    echo "  1) .env DATABASE_URL" > /dev/tty
    echo "  2) local compose DB" > /dev/tty
    echo "  3) local compose DB by name" > /dev/tty
    echo "  4) custom DATABASE_URL" > /dev/tty
    source_choice=$(prompt_value "Source" "$detected_default")

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
        echo "Invalid source choice: $source_choice" >&2
        exit 1
        ;;
    esac
  fi

  if [ -z "$EXPLICIT_FORMAT" ]; then
    echo "" > /dev/tty
    echo "Choose format:" > /dev/tty
    echo "  1) custom (.dump, recommended for backups/restore)" > /dev/tty
    echo "  2) sql (.sql, readable text)" > /dev/tty
    format_choice=$(prompt_value "Format" "1")
    case "$format_choice" in
      1|custom|dump)
        FORMAT=custom
        ;;
      2|sql)
        FORMAT=sql
        ;;
      *)
        echo "Invalid format choice: $format_choice" >&2
        exit 1
        ;;
    esac
  fi

  if [ -z "$EXPLICIT_EXCLUDE_TABLES" ]; then
    if prompt_yes_no "Exclude temporary snapshot tables (_emb_snapshot_*)" "y"; then
      EXCLUDE_TABLES="_emb_snapshot_*"
    fi
  fi
}

if [ "$is_interactive" = "1" ]; then
  run_interactive_wizard
fi

if [ -z "$FORMAT" ]; then
  FORMAT=sql
fi

case "$FORMAT" in
  sql|custom)
    ;;
  *)
    echo "Unsupported FORMAT: $FORMAT. Use 'sql' or 'custom'." >&2
    exit 1
    ;;
esac

# Decide source mode after interactive choices and .env loading.
SOURCE_MODE=local
SOURCE_LABEL=scenegraph
if [ -n "$DB_NAME" ]; then
  SOURCE_MODE=local
  DB_NAME=$(safe_database_label "$DB_NAME")
  if [ -z "$DB_NAME" ]; then
    DB_NAME=scenegraph
  fi
  SOURCE_LABEL=$DB_NAME
elif [ -n "$DATABASE_URL" ]; then
  url_host=$(database_url_host "$DATABASE_URL")
  if is_local_database_host "$url_host"; then
    SOURCE_MODE=local
    DB_NAME=$(safe_database_label "$(database_url_database "$DATABASE_URL")")
    if [ -z "$DB_NAME" ]; then
      DB_NAME=scenegraph
    fi
    SOURCE_LABEL=$DB_NAME
  else
    SOURCE_MODE=remote
    SOURCE_LABEL=$(database_url_label "$DATABASE_URL")
  fi
fi

if [ "$is_interactive" != "1" ] \
  && [ "$SOURCE_MODE" = "remote" ] \
  && [ -z "$EXPLICIT_DATABASE_URL" ] \
  && [ -z "$EXPLICIT_DB_NAME" ] \
  && [ -z "$EXPLICIT_FORMAT" ] \
  && [ -z "$EXPLICIT_OUT" ] \
  && [ "$EXPORT_DUMP_NONINTERACTIVE" != "1" ]; then
  echo "Refusing non-interactive remote export from .env without explicit options." >&2
  echo "Run in a terminal, or pass FORMAT=custom/OUT=..., or set EXPORT_DUMP_NONINTERACTIVE=1." >&2
  exit 1
fi

DEFAULT_EXTENSION=sql
if [ "$FORMAT" = "custom" ]; then
  DEFAULT_EXTENSION=dump
fi

if [ -z "$OUT" ]; then
  DEFAULT_OUT="$PROJECT_ROOT/backend/data/backups/${SOURCE_LABEL}_${TIMESTAMP}.${DEFAULT_EXTENSION}"
  if [ "$is_interactive" = "1" ] && [ -z "$EXPLICIT_OUT" ]; then
    OUT=$(prompt_value "Output path" "$DEFAULT_OUT")
  else
    OUT=$DEFAULT_OUT
  fi
fi

# Write pg_dump output through a temporary file so failed exports never leave fake backups.
run_with_tmp_output() {
  out_file=$1
  shift
  tmp_out_file="${out_file}.tmp.$$"
  trap 'rm -f "$tmp_out_file"' EXIT INT TERM
  "$@" > "$tmp_out_file"
  mv "$tmp_out_file" "$out_file"
  trap - EXIT INT TERM
}

# Ask before exporting a database that looks empty or tiny.
confirm_non_empty_local_database() {
  if [ "$is_interactive" != "1" ]; then
    return 0
  fi

  table_count=$(docker compose exec -T -e TARGET_DB="$1" db sh -lc '
    psql -U "$POSTGRES_USER" -d "$TARGET_DB" -tAc "SELECT count(*) FROM information_schema.tables WHERE table_schema = '\''public'\'' AND table_type = '\''BASE TABLE'\'';" 2>/dev/null
  ' | tr -d "[:space:]")

  if [ -z "$table_count" ]; then
    table_count=0
  fi

  echo "Local database '$1' public table count: $table_count"
  if [ "$table_count" = "0" ]; then
    if ! prompt_yes_no "This local database looks empty. Continue exporting it anyway?" "n"; then
      echo "Export canceled."
      exit 0
    fi
  fi
}

# Export a database reachable through DATABASE_URL, usually AWS/RDS.
export_from_database_url() {
  mkdir -p "$(dirname "$OUT")"

  echo "Exporting remote database '$SOURCE_LABEL' through DATABASE_URL in format '$FORMAT'..."
  echo "Output: $OUT"

  if [ "$FORMAT" = "custom" ]; then
    format_arg=-Fc
  else
    format_arg=
  fi

  run_with_tmp_output "$OUT" docker run --rm \
    -e DATABASE_URL="$DATABASE_URL" \
    -e FORMAT_ARG="$format_arg" \
    -e EXCLUDE_TABLES="$EXCLUDE_TABLES" \
    "$PG_DUMP_IMAGE" \
    sh -lc '
      set -- --no-owner --no-privileges
      if [ -n "$FORMAT_ARG" ]; then
        set -- "$@" "$FORMAT_ARG"
      fi
      if [ -n "$EXCLUDE_TABLES" ]; then
        old_ifs=$IFS
        IFS=,
        for table_pattern in $EXCLUDE_TABLES; do
          if [ -n "$table_pattern" ]; then
            set -- "$@" "--exclude-table=$table_pattern"
          fi
        done
        IFS=$old_ifs
      fi
      pg_dump "$@" "$DATABASE_URL"
    '

  echo "Export complete: $OUT"
}

# Export from the local docker compose Postgres service.
export_from_local_compose_db() {
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

  target_db=$DB_NAME
  if [ -z "$target_db" ]; then
    target_db=$(docker compose exec -T db sh -lc 'printf "%s" "$POSTGRES_DB"')
  fi
  confirm_non_empty_local_database "$target_db"

  mkdir -p "$(dirname "$OUT")"

  echo "Exporting local compose database '$target_db' in format '$FORMAT'..."
  echo "Output: $OUT"

  if [ "$FORMAT" = "custom" ]; then
    format_arg=-Fc
  else
    format_arg=
  fi

  run_with_tmp_output "$OUT" docker compose exec -T \
    -e TARGET_DB="$target_db" \
    -e FORMAT_ARG="$format_arg" \
    -e EXCLUDE_TABLES="$EXCLUDE_TABLES" \
    db sh -lc '
      set -- --no-owner --no-privileges
      if [ -n "$FORMAT_ARG" ]; then
        set -- "$@" "$FORMAT_ARG"
      fi
      if [ -n "$EXCLUDE_TABLES" ]; then
        old_ifs=$IFS
        IFS=,
        for table_pattern in $EXCLUDE_TABLES; do
          if [ -n "$table_pattern" ]; then
            set -- "$@" "--exclude-table=$table_pattern"
          fi
        done
        IFS=$old_ifs
      fi
      pg_dump -U "$POSTGRES_USER" -d "$TARGET_DB" "$@"
    '

  echo "Export complete: $OUT"
}

if [ "$SOURCE_MODE" = "remote" ]; then
  export_from_database_url
else
  export_from_local_compose_db
fi
