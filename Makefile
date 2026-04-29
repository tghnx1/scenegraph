COMPOSE := docker compose
ENV_FILE := .env
ENV_EXAMPLE := .env.example

.PHONY: help env build up upd down stop restart logs ps health clean list fclean

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
	@curl -fsS http://localhost:8080/health && printf "\n"
	@printf "\nGET /api/venues\n"
	@curl -fsS http://localhost:8080/api/venues && printf "\n"

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