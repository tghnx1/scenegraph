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
REFRESH_EVENTS_JSON ?= backend/data/ra_berlin_past_events_2026.json
REFRESH_EVENTS_JSON_IN_CONTAINER ?= /app/data/ra_berlin_past_events_2026.json
REFRESH_ARTISTS_JSON ?= backend/data/artists.json
REFRESH_BIO_JSON ?= backend/data/artist_biographies.json
REFRESH_EXISTING_EVENT_IDS_FILE ?= backend/data/existing_ra_event_ids.txt
REFRESH_EXISTING_ARTIST_IDS_FILE ?= backend/data/existing_ra_artist_ids.txt
REFRESH_CDP_URL ?= http://localhost:9222
REFRESH_PIPELINE_ARGS ?=
CHECK_ARTIST_ID ?= 2178

.PHONY: help env build up upd upd-build down stop restart logs ps health prisma-migrate prisma-studio db-shell import-events backfill-normalized-texts backfill-lineup-residual backfill-artist-biographies extract-artist-tags generate-embeddings backfill-embedding-vectors validate-import refresh-data-check refresh-data-check-bio refresh-data-check-bio-embeddings import-dump export-dump clean reset-db list fclean

help:
	@printf "\n"
	@printf "Scene Graph docker helpers\n"
	@printf "\n"
	@printf "  make env      Create .env from .env.example if missing\n"
	@printf "  make build    Build containers\n"
	@printf "  make up       Start stack in foreground (runs migrations first)\n"
	@printf "  make upd      Start dev stack in background with Vite dev server\n"
	@printf "  make upd-build Start build stack in background with nginx serving frontend dist\n"
	@printf "  make down     Stop and remove containers\n"
	@printf "  make stop     Stop running containers\n"
	@printf "  make restart  Restart the stack in background\n"
	@printf "  make logs     Follow compose logs\n"
	@printf "  make ps       Show running services\n"
	@printf "  make health   Check nginx and API health endpoints\n"
	@printf "  make prisma-migrate Apply Prisma migrations to Postgres\n"
	@printf "  make prisma-studio  Open Prisma Studio on localhost:5555\n"
	@printf "  make db-shell Open a psql shell inside the Postgres container\n"
	@printf "  make import-events Import backend/data/ra_berlin_past_events_2026.json\n"
	@printf "  make backfill-normalized-texts Fill normalized lineup and biography text fields\n"
	@printf "  make backfill-lineup-residual Fill events.lineup_residual_text from lineup_raw\n"
	@printf "  make backfill-artist-biographies Fill artists.biography_normalized from biography\n"
	@printf "  make extract-artist-tags Extract structured artist tags from biographies with an LLM\n"
	@printf "  make generate-embeddings Generate recommendation embeddings (provider from .env)\n"
	@printf "  make backfill-embedding-vectors Backfill pgvector column and build ANN indexes\n"
	@printf "  make validate-import Run post-import integrity checks against the current DATABASE_URL\n"
	@printf "  make refresh-data-check Run pipeline + import + validate on a check DB (default: scenegraph_check)\n"
	@printf "  make refresh-data-check-bio Same as refresh-data-check, but includes artists biographies scraping\n"
	@printf "  make refresh-data-check-bio-embeddings Same as refresh-data-check-bio + incremental embeddings for check DB\n"
	@printf "  make import-dump   Import local/remote dump with interactive safety prompts\n"
	@printf "  make export-dump   Export DB_NAME or .env/explicit DATABASE_URL dump; supports OUT=... FORMAT=sql|custom\n"
	@printf "  make clean    Stop stack and remove containers (keeps DB volumes)\n"
	@printf "  make reset-db DANGEROUS: remove containers and DB volumes (requires RESET_DB=yes)\n"
	@printf "  make list     List Docker resources\n"
	@printf "  make fclean   Remove containers, images, volumes, and builder cache\n"
	@printf "\n"

env:
	@if [ ! -f "$(ENV_FILE)" ]; then \
		cp "$(ENV_EXAMPLE)" "$(ENV_FILE)"; \
		echo "Created $(ENV_FILE) from $(ENV_EXAMPLE)"; \
	else \
		echo "$(ENV_FILE) already exists"; \
	fi

build: env
	$(COMPOSE) build

up: env prisma-migrate
	$(COMPOSE) up --build

upd: env prisma-migrate
	$(COMPOSE) up --build -d

upd-build: env
	$(COMPOSE_BUILD) --profile tools run --rm --build prisma
	$(COMPOSE_BUILD) up --build -d --remove-orphans

down:
	$(COMPOSE) down

stop:
	$(COMPOSE) stop

restart: down upd

logs:
	$(COMPOSE) logs -f

ps:
	$(COMPOSE) ps

health:
	@printf "GET /health\n"
	@curl -fsS http://localhost:8080/health && printf "\n"
	@printf "\nGET /api/venues\n"
	@curl -fsS http://localhost:8080/api/venues && printf "\n"

prisma-migrate: env
	$(COMPOSE) --profile tools run --rm --build prisma

prisma-studio: env
	$(COMPOSE) --profile tools run --rm --build --service-ports prisma npx prisma studio --hostname 0.0.0.0 --port 5555

db-shell: env
	$(COMPOSE) exec db psql -U "$$POSTGRES_USER" -d "$$POSTGRES_DB"

import-events: env
	$(COMPOSE) exec backend python scripts/import_events.py

backfill-normalized-texts: env
	$(COMPOSE) exec backend python scripts/backfill_normalized_texts.py

backfill-lineup-residual: env
	$(COMPOSE) exec backend python scripts/backfill_normalized_texts.py --target lineup

backfill-artist-biographies: env
	$(COMPOSE) exec backend python scripts/backfill_normalized_texts.py --target biography

extract-artist-tags: env
	$(COMPOSE) exec backend python scripts/extract_artist_tags.py

generate-embeddings: env
	$(COMPOSE) exec backend python scripts/generate_embeddings.py

backfill-embedding-vectors: env
	$(COMPOSE) exec backend python scripts/backfill_embedding_vectors.py

validate-import: env
	$(COMPOSE) exec backend python scripts/validate_import.py

refresh-data-check: env
	@mkdir -p backend/data
	@test -x "$(REFRESH_PARSE_PYTHON)" || (echo "Missing parser Python: $(REFRESH_PARSE_PYTHON). Create backend venv or override REFRESH_PARSE_PYTHON."; exit 1)
	$(COMPOSE) exec -T -e DATABASE_URL="$(CHECK_DATABASE_URL)" backend python -c "import os,psycopg; conn=psycopg.connect(os.environ['DATABASE_URL']); cur=conn.cursor(); cur.execute(\"SELECT ra_event_id FROM events WHERE ra_event_id IS NOT NULL\"); print(\"\\n\".join(str(r[0]) for r in cur.fetchall())); conn.close()" > "$(REFRESH_EXISTING_EVENT_IDS_FILE)"
	$(COMPOSE) exec -T -e DATABASE_URL="$(CHECK_DATABASE_URL)" backend python -c "import os,psycopg; conn=psycopg.connect(os.environ['DATABASE_URL']); cur=conn.cursor(); cur.execute(\"SELECT ra_artist_id FROM artists WHERE ra_artist_id IS NOT NULL\"); print(\"\\n\".join(str(r[0]) for r in cur.fetchall())); conn.close()" > "$(REFRESH_EXISTING_ARTIST_IDS_FILE)"
	$(PYTHON) parsers/run_ra_pipeline.py --parse-python "$(REFRESH_PARSE_PYTHON)" --events-json "$(REFRESH_EVENTS_JSON)" --artists-json "$(REFRESH_ARTISTS_JSON)" --bio-json "$(REFRESH_BIO_JSON)" --skip-bio --cdp-url "$(REFRESH_CDP_URL)" --dedup-events-file "$(REFRESH_EXISTING_EVENT_IDS_FILE)" --dedup-artists-file "$(REFRESH_EXISTING_ARTIST_IDS_FILE)" $(REFRESH_PIPELINE_ARGS)
	$(COMPOSE) exec -e DATABASE_URL="$(CHECK_DATABASE_URL)" backend python scripts/import_events.py "$(REFRESH_EVENTS_JSON_IN_CONTAINER)"
	$(COMPOSE) exec -e DATABASE_URL="$(CHECK_DATABASE_URL)" backend python scripts/validate_import.py --require-embeddings --check-artist-id "$(CHECK_ARTIST_ID)"

refresh-data-check-bio: env
	@mkdir -p backend/data
	@test -x "$(REFRESH_PARSE_PYTHON)" || (echo "Missing parser Python: $(REFRESH_PARSE_PYTHON). Create backend venv or override REFRESH_PARSE_PYTHON."; exit 1)
	@test -x "$(REFRESH_BIO_PYTHON)" || (echo "Missing bio Python: $(REFRESH_BIO_PYTHON). Create playwright venv or override REFRESH_BIO_PYTHON."; exit 1)
	@$(REFRESH_BIO_PYTHON) -c "import playwright" >/dev/null 2>&1 || (echo "Installing playwright in $(REFRESH_BIO_PYTHON) environment..."; $(REFRESH_BIO_PYTHON) -m pip install playwright)
	$(COMPOSE) exec -T -e DATABASE_URL="$(CHECK_DATABASE_URL)" backend python -c "import os,psycopg; conn=psycopg.connect(os.environ['DATABASE_URL']); cur=conn.cursor(); cur.execute(\"SELECT ra_event_id FROM events WHERE ra_event_id IS NOT NULL\"); print(\"\\n\".join(str(r[0]) for r in cur.fetchall())); conn.close()" > "$(REFRESH_EXISTING_EVENT_IDS_FILE)"
	$(COMPOSE) exec -T -e DATABASE_URL="$(CHECK_DATABASE_URL)" backend python -c "import os,psycopg; conn=psycopg.connect(os.environ['DATABASE_URL']); cur=conn.cursor(); cur.execute(\"SELECT ra_artist_id FROM artists WHERE ra_artist_id IS NOT NULL\"); print(\"\\n\".join(str(r[0]) for r in cur.fetchall())); conn.close()" > "$(REFRESH_EXISTING_ARTIST_IDS_FILE)"
	$(PYTHON) parsers/run_ra_pipeline.py --parse-python "$(REFRESH_PARSE_PYTHON)" --bio-python "$(REFRESH_BIO_PYTHON)" --events-json "$(REFRESH_EVENTS_JSON)" --artists-json "$(REFRESH_ARTISTS_JSON)" --bio-json "$(REFRESH_BIO_JSON)" --cdp-url "$(REFRESH_CDP_URL)" --dedup-events-file "$(REFRESH_EXISTING_EVENT_IDS_FILE)" --dedup-artists-file "$(REFRESH_EXISTING_ARTIST_IDS_FILE)" $(REFRESH_PIPELINE_ARGS)
	$(COMPOSE) exec -e DATABASE_URL="$(CHECK_DATABASE_URL)" backend python scripts/import_events.py "$(REFRESH_EVENTS_JSON_IN_CONTAINER)" --biographies-path "/app/data/artist_biographies.json"
	$(COMPOSE) exec -e DATABASE_URL="$(CHECK_DATABASE_URL)" backend python scripts/validate_import.py --require-embeddings --check-artist-id "$(CHECK_ARTIST_ID)" --biographies-path "/app/data/artist_biographies.json"

refresh-data-check-bio-embeddings: refresh-data-check-bio
	$(COMPOSE) exec -e DATABASE_URL="$(CHECK_DATABASE_URL)" backend python scripts/generate_embeddings.py

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
	rm .env

reset-db:
	@if [ "$$RESET_DB" != "yes" ]; then \
		echo "Refusing to delete database volumes."; \
		echo "Run: make reset-db RESET_DB=yes"; \
		exit 1; \
	fi
	$(COMPOSE) down -v

fclean:
	$(COMPOSE) down --rmi all -v --remove-orphans
	docker builder prune -f
	rm .env
