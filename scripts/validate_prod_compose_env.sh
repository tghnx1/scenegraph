#!/usr/bin/env bash

set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
compose_file="$repo_root/docker-compose.prod.yml"
docker_bin="$(command -v docker)"
temp_dir="$(mktemp -d)"
trap 'rm -rf "$temp_dir"' EXIT

required_variables=(
  DATABASE_URL
  JWT_SECRET_KEY
  PUBLIC_API_KEY
  OPENAI_API_KEY
  OPENAI_EMBEDDING_MODEL
  OPENAI_EMBEDDING_DIMENSIONS
  AZURE_OPENAI_API_KEY
  AZURE_OPENAI_ENDPOINT
  AZURE_OPENAI_CHAT_API_VERSION
  AZURE_OPENAI_EXTRACTION_DEPLOYMENT
)

complete_env="$temp_dir/complete.env"
cat >"$complete_env" <<'EOF'
DATABASE_URL=postgresql://compose_test:compose_test@example.invalid:5432/scenegraph
JWT_SECRET_KEY=compose-validation-jwt-secret
PUBLIC_API_KEY=compose-validation-public-api-key
OPENAI_API_KEY=compose-validation-openai-key
OPENAI_EMBEDDING_MODEL=text-embedding-3-small
OPENAI_EMBEDDING_DIMENSIONS=1536
AZURE_OPENAI_API_KEY=compose-validation-azure-key
AZURE_OPENAI_ENDPOINT=https://example.invalid
AZURE_OPENAI_CHAT_API_VERSION=2025-01-01-preview
AZURE_OPENAI_EXTRACTION_DEPLOYMENT=compose-validation-deployment
EOF

run_compose_config() {
  local env_file="$1"
  env -i \
    HOME="${HOME:-}" \
    PATH="$PATH" \
    DOCKER_CONFIG="${DOCKER_CONFIG:-${HOME:-}/.docker}" \
    "$docker_bin" compose \
      --project-directory "$repo_root" \
      --env-file "$env_file" \
      -f "$compose_file" \
      config
}

run_compose_config "$complete_env" >/dev/null
printf 'PASS complete production environment\n'

for variable in "${required_variables[@]}"; do
  missing_env="$temp_dir/missing-$variable.env"
  empty_env="$temp_dir/empty-$variable.env"
  error_output="$temp_dir/error-$variable.txt"

  grep -v "^${variable}=" "$complete_env" >"$missing_env"
  if run_compose_config "$missing_env" >/dev/null 2>"$error_output"; then
    printf 'FAIL missing %s was accepted\n' "$variable" >&2
    exit 1
  fi
  if ! grep -Fq "$variable is required" "$error_output"; then
    printf 'FAIL missing %s produced an unexpected error\n' "$variable" >&2
    cat "$error_output" >&2
    exit 1
  fi

  sed "s|^${variable}=.*$|${variable}=|" "$complete_env" >"$empty_env"
  if run_compose_config "$empty_env" >/dev/null 2>"$error_output"; then
    printf 'FAIL empty %s was accepted\n' "$variable" >&2
    exit 1
  fi
  if ! grep -Fq "$variable is required" "$error_output"; then
    printf 'FAIL empty %s produced an unexpected error\n' "$variable" >&2
    cat "$error_output" >&2
    exit 1
  fi

  printf 'PASS %s rejects missing and empty values\n' "$variable"
done
