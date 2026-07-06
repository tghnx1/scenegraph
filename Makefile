COMPOSE := docker compose
COMPOSE_BUILD := docker compose -f docker-compose.build.yml
ENV_FILE := .env
ENV_EXAMPLE := .env.example
PYTHON ?= python3
CHECK_DB_NAME ?= scenegraph_check
CHECK_DATABASE_URL ?= postgresql://scenegraph:change-me@db:5432/$(CHECK_DB_NAME)
PARSER_DATABASE_URL ?= postgresql://scenegraph:change-me@127.0.0.1:5432/$(CHECK_DB_NAME)
REFRESH_PARSE_PYTHON ?= $(abspath backend/.venv/bin/python)
REFRESH_BIO_PYTHON ?= $(abspath parsers/playwright_parser/venv/bin/python)
FULL_PIPELINE_MIN_DATE ?= 2021-01-01
FULL_PIPELINE_MAX_DATE ?=
FULL_PIPELINE_VALIDATE_ARTIST_ID ?=
FULL_PIPELINE_DEDUP_WITH_DB ?= yes
FULL_PIPELINE_SKIP_BIO ?= yes
FULL_PIPELINE_SKIP_TAGS ?= no
FULL_PIPELINE_SKIP_EMBEDDINGS ?= no
FULL_PIPELINE_EVENTS_JSON ?=
FULL_PIPELINE_ARTIFACTS_DIR ?= backend/data/import_runs
REFRESH_EVENTS_JSON ?= backend/data/ra_berlin_past_events_2026.json
REFRESH_EVENTS_JSON_IN_CONTAINER ?= /app/data/ra_berlin_past_events_2026.json
REFRESH_ARTISTS_JSON ?= backend/data/artists.json
REFRESH_BIO_JSON ?= backend/data/artist_biographies.json
REFRESH_EXISTING_EVENT_IDS_FILE ?= backend/data/existing_ra_event_ids.txt
REFRESH_EXISTING_ARTIST_IDS_FILE ?= backend/data/existing_ra_artist_ids.txt
REFRESH_CDP_URL ?= http://localhost:9222
REFRESH_PIPELINE_ARGS ?=
CHECK_ARTIST_ID ?= 2178
NGINX_CERT_DIR ?= nginx/certs
NGINX_CERT_KEY ?= $(NGINX_CERT_DIR)/privkey.pem
NGINX_CERT_FILE ?= $(NGINX_CERT_DIR)/fullchain.pem
CERT_NAMES ?=

.PHONY: help env cert build up upd upd-build debug-up debug-down down stop restart logs ps ensure-ssl-certs prisma-migrate db-shell full-pipeline import-dump export-dump clean list fclean

help:
	@printf "\n"
	@printf "Scene Graph docker helpers\n"
	@printf "\n"
	@printf "  make env      Create .env from .env.example if missing\n"
	@printf "  make cert     Generate nginx self-signed TLS certificate\n"
	@printf "                flags: CERT_NAMES='localhost 127.0.0.1'\n"
	@printf "  make build    Build local dev images only (usually unnecessary; make upd builds as needed)\n"
	@printf "  make up       Start local dev stack in foreground with recommendation-worker count from .env (fallback: 1)\n"
	@printf "                flags: RECOMMENDATION_WORKER=3\n"
	@printf "  make upd      Start local dev stack in background (recommended default)\n"
	@printf "                flags: RECOMMENDATION_WORKER=3\n"
	@printf "  make upd-build Start production-like stack in background with nginx serving built frontend dist\n"
	@printf "                flags: RECOMMENDATION_WORKER=3\n"
	@printf "  make debug-up Start stack with backend connecting to the PyCharm debug server on localhost:5678\n"
	@printf "                flags: RECOMMENDATION_WORKER=3 PYCHARM_DEBUG_HOST=host.docker.internal PYCHARM_DEBUG_PORT=5678 PYCHARM_DEBUG_SUSPEND=0\n"
	@printf "  make debug-down Stop the debug stack\n"
	@printf "  make down     Stop and remove containers\n"
	@printf "  make stop     Stop running containers\n"
	@printf "  make restart  Restart the stack in background\n"
	@printf "  make logs     Follow compose logs\n"
	@printf "  make ps       Show running services\n"
	@printf "  make prisma-migrate Apply Prisma migrations to Postgres\n"
	@printf "  make db-shell Open a psql shell inside the Postgres container\n"
	@printf "  make full-pipeline Preferred end-to-end import/enrichment flow in Docker\n"
	@printf "                flags: FULL_PIPELINE_MIN_DATE=2024-01-01 FULL_PIPELINE_MAX_DATE=2024-12-31\n"
	@printf "                       FULL_PIPELINE_EVENTS_JSON=backend/data/events.json FULL_PIPELINE_ARTIFACTS_DIR=backend/data/import_runs\n"
	@printf "                       FULL_PIPELINE_VALIDATE_ARTIST_ID=2178 FULL_PIPELINE_DEDUP_WITH_DB=yes|no\n"
	@printf "                       FULL_PIPELINE_SKIP_BIO=yes|no (default yes) FULL_PIPELINE_SKIP_TAGS=yes|no FULL_PIPELINE_SKIP_EMBEDDINGS=yes|no\n"
	@printf "  make import-dump   Import local/remote dump with interactive safety prompts\n"
	@printf "                flags: DUMP=/abs/path/dump.sql DUMP_FORMAT=sql|custom DB_NAME=scenegraph_check DATABASE_URL=postgresql://...\n"
	@printf "                       RESET_DB=1 PG_CLIENT_IMAGE=postgres:18 REMOTE_RESTORE_MODE=clean|data-only\n"
	@printf "                       CONFIRM_IMPORT=IMPORT-REMOTE IMPORT_DUMP_NONINTERACTIVE=1\n"
	@printf "  make export-dump   Export DB_NAME or .env/explicit DATABASE_URL dump\n"
	@printf "                flags: DB_NAME=scenegraph_check DATABASE_URL=postgresql://... OUT=/abs/path/backup.dump FORMAT=sql|custom\n"
	@printf "                       PG_DUMP_IMAGE=postgres:18 EXCLUDE_TABLES='_emb_snapshot_*' EXPORT_DUMP_NONINTERACTIVE=1\n"
	@printf "  make up/upd/upd-build auto-generate nginx SSL certs if nginx/certs is missing them\n"
	@printf "  make clean    Stop stack and remove containers (keeps DB volumes and preserves .env)\n"
	@printf "  make list     List Docker resources\n"
	@printf "  make fclean   Remove containers, images, volumes, and builder cache (preserves .env)\n"
	@printf "\n"

env:
	@if [ ! -f "$(ENV_FILE)" ]; then \
		cp "$(ENV_EXAMPLE)" "$(ENV_FILE)"; \
		echo "Created $(ENV_FILE) from $(ENV_EXAMPLE)"; \
	else \
		echo "$(ENV_FILE) already exists"; \
	fi

cert:
	./scripts/gen_cert.sh $(CERT_NAMES)

build: env
	$(COMPOSE) build

ensure-ssl-certs:
	@if [ ! -f "$(NGINX_CERT_KEY)" ] || [ ! -f "$(NGINX_CERT_FILE)" ]; then \
		echo "Missing nginx SSL certs; generating self-signed certificate..."; \
		./scripts/gen_cert.sh; \
	else \
		echo "nginx SSL certs already exist"; \
	fi

up: env ensure-ssl-certs prisma-migrate
	@set -a; [ -f .env ] && . ./.env; set +a; \
	$(COMPOSE) up --build --scale recommendation-worker="$${RECOMMENDATION_WORKER:-1}"

upd: env ensure-ssl-certs prisma-migrate
	@set -a; [ -f .env ] && . ./.env; set +a; \
	$(COMPOSE) up --build -d --scale recommendation-worker="$${RECOMMENDATION_WORKER:-1}"

upd-build: env ensure-ssl-certs
	$(COMPOSE_BUILD) --profile tools run --rm --build prisma
	@set -a; [ -f .env ] && . ./.env; set +a; \
	$(COMPOSE_BUILD) up --build -d --remove-orphans --scale recommendation-worker="$${RECOMMENDATION_WORKER:-1}"

debug-up: env ensure-ssl-certs prisma-migrate
	@set -a; [ -f .env ] && . ./.env; set +a; \
	$(COMPOSE) -f docker-compose.yml -f docker-compose.debug.yml up --build -d --scale recommendation-worker="$${RECOMMENDATION_WORKER:-1}" db backend recommendation-worker frontend nginx

debug-down:
	$(COMPOSE) -f docker-compose.yml -f docker-compose.debug.yml down --remove-orphans

down:
	$(COMPOSE) down

stop:
	$(COMPOSE) stop

restart: down upd

logs:
	$(COMPOSE) logs -f

ps:
	$(COMPOSE) ps

prisma-migrate: env
	$(COMPOSE) --profile tools run --rm --build prisma

db-shell: env
	$(COMPOSE) exec db psql -U "$$POSTGRES_USER" -d "$$POSTGRES_DB"

full-pipeline: env
	FULL_PIPELINE_MIN_DATE="$(FULL_PIPELINE_MIN_DATE)" \
	FULL_PIPELINE_MAX_DATE="$(FULL_PIPELINE_MAX_DATE)" \
	FULL_PIPELINE_ARTIFACTS_DIR="$(FULL_PIPELINE_ARTIFACTS_DIR)" \
	FULL_PIPELINE_EVENTS_JSON="$(FULL_PIPELINE_EVENTS_JSON)" \
	FULL_PIPELINE_DEDUP_WITH_DB="$(FULL_PIPELINE_DEDUP_WITH_DB)" \
	FULL_PIPELINE_SKIP_BIO="$(FULL_PIPELINE_SKIP_BIO)" \
	FULL_PIPELINE_SKIP_TAGS="$(FULL_PIPELINE_SKIP_TAGS)" \
	FULL_PIPELINE_SKIP_EMBEDDINGS="$(FULL_PIPELINE_SKIP_EMBEDDINGS)" \
	FULL_PIPELINE_VALIDATE_ARTIST_ID="$(FULL_PIPELINE_VALIDATE_ARTIST_ID)" \
	./scripts/full_pipeline.sh

import-dump: env
	@DUMP="$(DUMP)" DB_NAME="$(DB_NAME)" DATABASE_URL="$(DATABASE_URL)" RESET_DB="$(RESET_DB)" DUMP_FORMAT="$(DUMP_FORMAT)" PG_CLIENT_IMAGE="$(PG_CLIENT_IMAGE)" REMOTE_RESTORE_MODE="$(REMOTE_RESTORE_MODE)" CONFIRM_IMPORT="$(CONFIRM_IMPORT)" IMPORT_DUMP_NONINTERACTIVE="$(IMPORT_DUMP_NONINTERACTIVE)" sh ./scripts/import_dump.sh

export-dump: env
	@DB_NAME="$(DB_NAME)" OUT="$(OUT)" FORMAT="$(FORMAT)" PG_DUMP_IMAGE="$(PG_DUMP_IMAGE)" EXCLUDE_TABLES="$(EXCLUDE_TABLES)" sh ./scripts/export_dump.sh

list:
	@printf "%b\n" "${BLU}== Images ==${RES}" && docker images
	@printf "%b\n" "${RED}== Containers ==${RES}" && docker ps -a
	@printf "%b\n" "${GRE}== Volumes ==${RES}" && docker volume ls
	@printf "%b\n" "${YEL}== Networks ==${RES}" && docker network ls
	@printf "%b\n" "${MAG}== Container PID 1 ==${RES}"
	@docker ps --format "{{.Names}}" | while read container; do \
		cmd=$$(docker exec $$container cat /proc/1/cmdline 2>/dev/null | tr '\0' ' ' || echo "N/A"); \
		printf "%s\t%s\n" "$$container" "$$cmd"; \
	done

clean:
	$(COMPOSE) down --remove-orphans

fclean:
	$(COMPOSE) down --rmi all -v --remove-orphans
	docker builder prune -f
