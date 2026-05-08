COMPOSE := docker compose
ENV_FILE := .env
ENV_EXAMPLE := .env.example

.PHONY: help env build up upd down stop restart logs ps health prisma-migrate prisma-studio db-shell clean

help:
	@printf "\n"
	@printf "Scene Graph docker helpers\n"
	@printf "\n"
	@printf "  make env      Create .env from .env.example if missing\n"
	@printf "  make build    Build containers\n"
	@printf "  make up       Start stack in foreground\n"
	@printf "  make upd      Start stack in background\n"
	@printf "  make down     Stop and remove containers\n"
	@printf "  make stop     Stop running containers\n"
	@printf "  make restart  Restart the stack in background\n"
	@printf "  make logs     Follow compose logs\n"
	@printf "  make ps       Show running services\n"
	@printf "  make health   Check nginx and API health endpoints\n"
	@printf "  make prisma-migrate Apply Prisma migrations to Postgres\n"
	@printf "  make prisma-studio  Open Prisma Studio on localhost:5555\n"
	@printf "  make db-shell Open a psql shell inside the Postgres container\n"
	@printf "  make clean    Stop stack and remove volumes\n"
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

logs:
	$(COMPOSE) logs -f

ps:
	$(COMPOSE) ps

health:
	@printf "GET /health\n"
	@curl -fsS http://localhost/health && printf "\n"
	@printf "\nGET /api/venues\n"
	@curl -fsS http://localhost/api/venues && printf "\n"

prisma-migrate: env
	$(COMPOSE) --profile tools run --rm --build prisma

prisma-studio: env
	$(COMPOSE) --profile tools run --rm --build --service-ports prisma npx prisma studio --hostname 0.0.0.0 --port 5555

db-shell: env
	$(COMPOSE) exec db psql -U "$$POSTGRES_USER" -d "$$POSTGRES_DB"

clean:
	$(COMPOSE) down -v
