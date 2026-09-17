# =============================================================================
# GenAssist Makefile
# =============================================================================
# Convenient commands for Docker operations and development
#
# Usage: make <target>
# Run 'make help' to see all available commands
# =============================================================================

.PHONY: help
.DEFAULT_GOAL := help

# Colors for terminal output
CYAN := \033[36m
GREEN := \033[32m
YELLOW := \033[33m
RED := \033[31m
RESET := \033[0m

# Docker Compose files (base + override pattern)
DOCKER_DIR := docker
COMPOSE_BASE := $(DOCKER_DIR)/docker-compose.base.yml
COMPOSE_PROD := $(DOCKER_DIR)/docker-compose.yml
COMPOSE_DEV := $(DOCKER_DIR)/docker-compose.build.yml
COMPOSE_CI := $(DOCKER_DIR)/docker-compose.ci.yml

# Compose command shortcuts
DC_PROD := docker compose -f $(COMPOSE_BASE) -f $(COMPOSE_PROD)
DC_DEV := docker compose -f $(COMPOSE_BASE) -f $(COMPOSE_DEV)
DC_CI := docker compose -f $(COMPOSE_BASE) -f $(COMPOSE_CI)

# =============================================================================
# HELP
# =============================================================================

help: ## Show this help message
	@echo "$(CYAN)GenAssist Docker Commands$(RESET)"
	@echo ""
	@echo "$(GREEN)Usage:$(RESET) make $(YELLOW)<target>$(RESET)"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  $(YELLOW)%-20s$(RESET) %s\n", $$1, $$2}'
	@echo ""
	@echo "$(GREEN)Examples:$(RESET)"
	@echo "  make dev              # Start full dev environment"
	@echo "  make services         # Start only infrastructure"
	@echo "  make up-db            # Start only database"
	@echo "  make logs-app         # View app logs"

# =============================================================================
# PRODUCTION COMMANDS (Pre-built images from GHCR)
# =============================================================================

prod: ## Start full production stack
	$(DC_PROD) --profile full up -d

prod-backend: ## Start production backend only
	$(DC_PROD) --profile backend up -d

prod-frontend: ## Start production frontend only
	$(DC_PROD) --profile frontend up -d

prod-down: ## Stop production stack
	$(DC_PROD) --profile full down

prod-logs: ## View production logs
	$(DC_PROD) --profile full logs -f

# =============================================================================
# DEVELOPMENT COMMANDS (Build from source)
# =============================================================================

dev: ## Start full development stack with build
	$(DC_DEV) --profile full up -d --build

dev-backend: ## Start development backend only
	$(DC_DEV) --profile backend up -d --build

dev-frontend: ## Start development frontend only
	$(DC_DEV) --profile frontend up -d --build

dev-no-build: ## Start development stack without rebuilding
	$(DC_DEV) --profile full up -d

dev-down: ## Stop development stack
	$(DC_DEV) --profile full down

dev-down-v: ## Stop development stack and remove volumes
	$(DC_DEV) --profile full down -v

dev-logs: ## View development logs
	$(DC_DEV) --profile full logs -f

dev-build: ## Build development images
	$(DC_DEV) build

dev-build-app: ## Build only backend image
	$(DC_DEV) build app

dev-build-ui: ## Build only frontend image
	$(DC_DEV) build ui

# =============================================================================
# CI/CD COMMANDS
# =============================================================================

ci: ## Start CI stack
	$(DC_CI) --profile full up -d --build

ci-backend: ## Start CI backend only
	$(DC_CI) --profile backend up -d --build

ci-down: ## Stop CI stack and cleanup
	$(DC_CI) --profile full down -v --remove-orphans

ci-logs: ## View CI logs
	$(DC_CI) --profile full logs -f

# =============================================================================
# SERVICES ONLY (Infrastructure for local IDE development)
# =============================================================================

services: ## Start all infrastructure services (db, redis, chroma, qdrant, whisper)
	$(DC_DEV) up -d db redis chroma qdrant whisper

services-down: ## Stop infrastructure services
	$(DC_DEV) stop db redis chroma qdrant whisper

services-down-v: ## Stop infrastructure and remove volumes
	$(DC_DEV) down -v

services-logs: ## View infrastructure logs
	$(DC_DEV) logs -f db redis chroma qdrant whisper

# =============================================================================
# INDIVIDUAL SERVICE COMMANDS
# =============================================================================

up-db: ## Start only database
	$(DC_DEV) up -d db

up-redis: ## Start only Redis
	$(DC_DEV) up -d redis

up-chroma: ## Start only Chroma
	$(DC_DEV) up -d chroma

up-qdrant: ## Start only Qdrant
	$(DC_DEV) up -d qdrant

up-whisper: ## Start only Whisper
	$(DC_DEV) up -d whisper

up-core: ## Start db and redis
	$(DC_DEV) up -d db redis

up-vectordb: ## Start all vector databases
	$(DC_DEV) up -d chroma qdrant

up-all-services: ## Start db, redis, chroma, qdrant, whisper
	$(DC_DEV) up -d db redis chroma qdrant whisper

# =============================================================================
# LOGS COMMANDS
# =============================================================================

logs-app: ## View app container logs
	docker logs -f genassist-app-dev 2>/dev/null || docker logs -f genassist-app 2>/dev/null || echo "App container not found"

logs-db: ## View database logs
	docker logs -f genassist-db-local 2>/dev/null || docker logs -f genassist-db-dev 2>/dev/null || docker logs -f genassist-db 2>/dev/null || echo "DB container not found"

logs-redis: ## View Redis logs
	docker logs -f genassist-redis-local 2>/dev/null || docker logs -f genassist-redis-dev 2>/dev/null || docker logs -f genassist-redis 2>/dev/null || echo "Redis container not found"

logs-celery: ## View Celery worker logs
	docker logs -f genassist-celery-worker-dev 2>/dev/null || docker logs -f genassist-celery-worker 2>/dev/null || echo "Celery worker container not found"

logs-flower: ## View Flower logs
	docker logs -f genassist-flower-dev 2>/dev/null || docker logs -f genassist-flower 2>/dev/null || echo "Flower container not found"

logs-whisper: ## View Whisper logs
	docker logs -f genassist-whisper-local 2>/dev/null || docker logs -f genassist-whisper-dev 2>/dev/null || docker logs -f genassist-whisper 2>/dev/null || echo "Whisper container not found"

# =============================================================================
# TESTING COMMANDS
# =============================================================================

test-ui: ## Run UI tests
	$(DC_DEV) --profile testing up uitests

test-backend: ## Run backend tests in container
	$(DC_DEV) exec app python -m pytest tests/ -v

# =============================================================================
# UTILITY COMMANDS
# =============================================================================

ps: ## Show running containers
	$(DC_DEV) ps 2>/dev/null || $(DC_PROD) ps

shell-app: ## Shell into app container
	docker exec -it genassist-app-dev /bin/bash 2>/dev/null || docker exec -it genassist-app /bin/bash

shell-db: ## Shell into database container
	docker exec -it genassist-db-local psql -U postgres -d core_db 2>/dev/null || docker exec -it genassist-db-dev psql -U postgres -d core_db 2>/dev/null || docker exec -it genassist-db psql -U postgres -d core_db

clean: ## Remove all GenAssist containers, networks, and images
	@echo "$(YELLOW)Stopping all GenAssist containers...$(RESET)"
	-$(DC_DEV) --profile full down -v --remove-orphans 2>/dev/null
	-$(DC_PROD) --profile full down -v --remove-orphans 2>/dev/null
	-$(DC_CI) --profile full down -v --remove-orphans 2>/dev/null
	@echo "$(YELLOW)Removing GenAssist images...$(RESET)"
	-docker images | grep genassist | awk '{print $$3}' | xargs -r docker rmi -f 2>/dev/null
	@echo "$(GREEN)Cleanup complete!$(RESET)"

clean-volumes: ## Remove all GenAssist volumes
	@echo "$(YELLOW)Removing GenAssist volumes...$(RESET)"
	-docker volume ls | grep genassist | awk '{print $$2}' | xargs -r docker volume rm 2>/dev/null
	@echo "$(GREEN)Volume cleanup complete!$(RESET)"

prune: ## Docker system prune (remove unused data)
	docker system prune -f
	docker volume prune -f

# =============================================================================
# SETUP COMMANDS
# =============================================================================

setup-env: ## Copy example environment files
	@echo "$(CYAN)Setting up environment files...$(RESET)"
	@if [ ! -f backend/.env ]; then cp backend/.env.example backend/.env && echo "$(GREEN)Created backend/.env$(RESET)"; else echo "$(YELLOW)backend/.env already exists$(RESET)"; fi
	@if [ ! -f frontend/.env ]; then cp frontend/.env.template frontend/.env && echo "$(GREEN)Created frontend/.env$(RESET)"; else echo "$(YELLOW)frontend/.env already exists$(RESET)"; fi
	@if [ ! -f docker/.env ]; then cp docker/.env.example docker/.env && echo "$(GREEN)Created docker/.env$(RESET)"; else echo "$(YELLOW)docker/.env already exists$(RESET)"; fi
	@echo "$(GREEN)Environment setup complete! Please update the .env files with your configuration.$(RESET)"

# =============================================================================
# QUICK START
# =============================================================================

quickstart: setup-env services ## Quick start: setup env and start services
	@echo ""
	@echo "$(GREEN)Infrastructure services are starting!$(RESET)"
	@echo ""
	@echo "$(CYAN)Next steps:$(RESET)"
	@echo "  1. Update backend/.env and frontend/.env with your configuration"
	@echo "  2. Run 'make dev' to start the full application"
	@echo "  3. Access the app at http://localhost:8080"
	@echo ""
