# Makefile — Odyssey RAG build/test/run shortcuts
.PHONY: up down build logs logs-api seed shell db-shell test test-unit test-integration lint format check migrate db-migrate db-reset clean

# ── Docker ────────────────────────────────────────
up:                              ## Start all services
	docker compose up -d

down:                            ## Stop all services
	docker compose down

build:                           ## Build/rebuild images
	docker compose build --no-cache

logs:                            ## Tail all service logs
	docker compose logs -f

logs-api:                        ## Tail RAG API logs
	docker compose logs -f rag-api

# ── Development ───────────────────────────────────
dev:                             ## Start with hot-reload + exposed ports
	docker compose up

seed:                            ## Run initial source ingestion
	docker compose exec rag-api python scripts/seed_initial_sources.py

shell:                           ## Open shell in API container
	docker compose exec rag-api bash

db-shell:                        ## Open psql in database
	docker compose exec postgres psql -U $${POSTGRES_USER:-rag_user} -d $${POSTGRES_DB:-odyssey_rag}

# ── Testing ───────────────────────────────────────
test:                            ## Run all tests inside container
	docker compose run --rm -e ENVIRONMENT=test rag-api pytest tests/ -v

test-unit:                       ## Run unit tests only
	docker compose run --rm -e ENVIRONMENT=test rag-api pytest tests/unit/ -v

test-integration:                ## Run integration tests only
	docker compose run --rm -e ENVIRONMENT=test rag-api pytest tests/integration/ -v

test-eval:                       ## Run evaluation set
	docker compose run --rm -e ENVIRONMENT=test rag-api pytest tests/evaluation/ -v

# ── Quality ───────────────────────────────────────
lint:                            ## Run ruff linter + mypy
	docker compose run --rm rag-api ruff check src/ tests/

format:                          ## Auto-format code
	docker compose run --rm rag-api ruff format src/ tests/

check:                           ## Lint + test (CI gate)
	@$(MAKE) lint
	@$(MAKE) test

# ── Database ──────────────────────────────────────
migrate:                         ## Run Alembic migrations (upgrade head)
	cd "$(CURDIR)" && alembic upgrade head

db-migrate:                      ## Run pending migrations (legacy)
	docker compose exec rag-api python scripts/migrate.py

db-reset:                        ## Drop and recreate database
	docker compose down -v
	docker compose up -d postgres
	@echo "Waiting for postgres..."
	@sleep 5
	docker compose up -d

# ── Cleanup ───────────────────────────────────────
clean:                           ## Remove containers, volumes, images
	docker compose down -v --rmi local

# ── Help ──────────────────────────────────────────
help:                            ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

.DEFAULT_GOAL := help
