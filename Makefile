COMPOSE := docker compose
ENV_FILE := .env
ENV_EXAMPLE := .env.example

.PHONY: help env build up upd down stop restart logs ps health frontend-dev prisma-migrate prisma-studio db-shell import-events import-dump clean list fclean

help:
	@printf "\n"
	@printf "Scene Graph docker helpers\n"
	@printf "\n"
	@printf "  make env      Create .env from .env.example if missing\n"
	@printf "  make build    Build containers\n"
	@printf "  make up       Start stack in foreground\n"
	@printf "  make upd      Start stack in background\n"
	@printf "  make frontend-dev Start live frontend dev container\n"
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
	@printf "  make import-dump   Import a local SQL dump; prompts before overwrite\n"
	@printf "  make clean    Stop stack and remove volumes\n"
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

up: env
	$(COMPOSE) up --build

upd: env
	$(COMPOSE) up --build -d

down:
	$(COMPOSE) down

stop:
	$(COMPOSE) stop

restart: down upd

frontend-dev: env
	$(COMPOSE) up -d frontend nginx

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

import-dump: env
	DUMP="$(DUMP)" RESET_DB="$(RESET_DB)" ./scripts/import_dump.sh

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
	$(COMPOSE) down -v

fclean:
	$(COMPOSE) down --rmi all -v --remove-orphans
	docker builder prune -f
