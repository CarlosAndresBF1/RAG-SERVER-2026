# Odyssey RAG — Docker Setup

> **Version**: 1.0.0  
> **Date**: 2026-03-02  
> **Status**: Planning  
> **Ref**: [ARCHITECTURE.md](ARCHITECTURE.md) §5

---

## 1. Service Topology

```
┌─────────────────────────────────────────────────────────┐
│  docker compose up                                       │
│                                                         │
│  ┌────────────┐  ┌────────────┐  ┌────────────────────┐ │
│  │  postgres   │  │  rag-api   │  │  mcp-server        │ │
│  │  :5432      │←─│  :8080     │←─│  :3000 (HTTP/SSE)  │ │
│  │  pgvector   │  │  FastAPI   │  │  + stdio            │ │
│  └────────────┘  └────────────┘  └────────────────────┘ │
│                                                         │
│  Volume: pgdata          Volume: rag-models             │
│          sources-data             api-cache              │
└─────────────────────────────────────────────────────────┘
```

---

## 2. docker-compose.yml

```yaml
# docker-compose.yml
version: "3.9"

services:
  # ─── PostgreSQL + pgvector ──────────────────────────────
  postgres:
    image: pgvector/pgvector:0.7.4-pg16
    container_name: odyssey-rag-db
    restart: unless-stopped
    environment:
      POSTGRES_DB: ${POSTGRES_DB:-odyssey_rag}
      POSTGRES_USER: ${POSTGRES_USER:-rag_user}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:?POSTGRES_PASSWORD required}
    ports:
      - "${POSTGRES_PORT:-5432}:5432"
    volumes:
      - pgdata:/var/lib/postgresql/data
      - ./db/init:/docker-entrypoint-initdb.d:ro
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER:-rag_user} -d ${POSTGRES_DB:-odyssey_rag}"]
      interval: 5s
      timeout: 3s
      retries: 5
    networks:
      - rag-net

  # ─── RAG API (FastAPI) ─────────────────────────────────
  rag-api:
    build:
      context: .
      dockerfile: Dockerfile
      target: api
    container_name: odyssey-rag-api
    restart: unless-stopped
    depends_on:
      postgres:
        condition: service_healthy
    environment:
      # Database
      DATABASE_URL: postgresql+asyncpg://${POSTGRES_USER:-rag_user}:${POSTGRES_PASSWORD}@postgres:5432/${POSTGRES_DB:-odyssey_rag}
      
      # Embeddings (local nomic-embed-text)
      EMBEDDING_PROVIDER: nomic-local
      EMBEDDING_MODEL: nomic-embed-text-v1.5
      EMBEDDING_DIMENSION: "768"
      
      # LLM provider
      LLM_PROVIDER: ${LLM_PROVIDER:-openai}
      OPENAI_API_KEY: ${OPENAI_API_KEY:-}
      ANTHROPIC_API_KEY: ${ANTHROPIC_API_KEY:-}
      GOOGLE_API_KEY: ${GOOGLE_API_KEY:-}
      
      # Reranker
      RERANKER_MODEL: cross-encoder/ms-marco-MiniLM-L-6-v2
      
      # App
      LOG_LEVEL: ${LOG_LEVEL:-info}
      ENVIRONMENT: ${ENVIRONMENT:-development}
    ports:
      - "${RAG_API_PORT:-8080}:8080"
    volumes:
      - rag-models:/app/models          # Cached model weights
      - ./data/sources:/app/sources:ro  # Source documents (read-only)
    healthcheck:
      test: ["CMD", "python", "-c", "import httpx; httpx.get('http://localhost:8080/health').raise_for_status()"]
      interval: 10s
      timeout: 5s
      retries: 3
      start_period: 30s
    networks:
      - rag-net

  # ─── MCP Server ────────────────────────────────────────
  mcp-server:
    build:
      context: .
      dockerfile: Dockerfile
      target: mcp
    container_name: odyssey-mcp-server
    restart: unless-stopped
    depends_on:
      rag-api:
        condition: service_healthy
    environment:
      RAG_API_URL: http://rag-api:8080
      MCP_TRANSPORT: ${MCP_TRANSPORT:-http}
      MCP_PORT: "3000"
      LOG_LEVEL: ${LOG_LEVEL:-info}
    ports:
      - "${MCP_PORT:-3000}:3000"
    networks:
      - rag-net

volumes:
  pgdata:
    driver: local
  rag-models:
    driver: local

networks:
  rag-net:
    driver: bridge
```

---

## 3. Dockerfile (Multi-Stage)

```dockerfile
# Dockerfile
# ── Stage 1: Base Python ──────────────────────────────
FROM python:3.11-slim AS base

WORKDIR /app

# System dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Python dependencies
COPY requirements.txt requirements-dev.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy source
COPY src/ ./src/
COPY config/ ./config/
COPY scripts/ ./scripts/
COPY db/ ./db/

ENV PYTHONPATH=/app/src
ENV PYTHONUNBUFFERED=1

# ── Stage 2: RAG API ─────────────────────────────────
FROM base AS api

# Download embedding model on build (cached in layer)
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('nomic-ai/nomic-embed-text-v1.5')"
RUN python -c "from sentence_transformers import CrossEncoder; CrossEncoder('cross-encoder/ms-marco-MiniLM-L-6-v2')"

EXPOSE 8080

CMD ["uvicorn", "odyssey_rag.api.main:app", "--host", "0.0.0.0", "--port", "8080", "--workers", "2"]

# ── Stage 3: MCP Server ──────────────────────────────
FROM base AS mcp

EXPOSE 3000

CMD ["python", "-m", "odyssey_rag.mcp_server.main"]

# ── Stage 4: Dev (all tools) ─────────────────────────
FROM base AS dev

RUN pip install --no-cache-dir -r requirements-dev.txt

# Download models
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('nomic-ai/nomic-embed-text-v1.5')"
RUN python -c "from sentence_transformers import CrossEncoder; CrossEncoder('cross-encoder/ms-marco-MiniLM-L-6-v2')"

CMD ["bash"]
```

---

## 4. Database Init Scripts

Files in `db/init/` run automatically on first `docker compose up`:

### 4.1 `001_extensions.sql`

```sql
-- db/init/001_extensions.sql
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;
```

### 4.2 `002_schema.sql`

Full DDL from [DATA_MODEL.md](DATA_MODEL.md) §3 — creates all 6 tables, indexes, triggers.

### 4.3 `003_seed_config.sql`

```sql
-- db/init/003_seed_config.sql
-- Optional: seed any initial configuration rows
-- (empty for now, acts as placeholder for future config tables)
```

---

## 5. Environment Configuration

### 5.1 `.env.example`

```bash
# .env.example — Copy to .env and fill in values

# ── Database ──────────────────────────────
POSTGRES_DB=odyssey_rag
POSTGRES_USER=rag_user
POSTGRES_PASSWORD=         # REQUIRED: set a strong password
POSTGRES_PORT=5432

# ── RAG API ───────────────────────────────
RAG_API_PORT=8080
LOG_LEVEL=info
ENVIRONMENT=development     # development | staging | production

# ── LLM Provider ─────────────────────────
LLM_PROVIDER=openai         # openai | anthropic | gemini
OPENAI_API_KEY=             # Required if LLM_PROVIDER=openai
ANTHROPIC_API_KEY=          # Required if LLM_PROVIDER=anthropic
GOOGLE_API_KEY=             # Required if LLM_PROVIDER=gemini

# ── MCP Server ────────────────────────────
MCP_TRANSPORT=http          # http | stdio
MCP_PORT=3000
```

### 5.2 `.env` Loading Order

1. `.env` file (docker compose auto-loads)
2. Environment variables from host (override .env)
3. Defaults in docker-compose.yml (fallback)

---

## 6. Volume Mapping

| Volume | Purpose | Mount |
|--------|---------|-------|
| `pgdata` | PostgreSQL data persistence | `/var/lib/postgresql/data` |
| `rag-models` | Cached embedding/reranker model weights | `/app/models` |
| `./db/init` | Init SQL scripts (bind mount, read-only) | `/docker-entrypoint-initdb.d` |
| `./data/sources` | Source documents for ingestion (bind mount, read-only) | `/app/sources` |

---

## 7. Networking

| Service | Internal Hostname | Internal Port | External Port |
|---------|-------------------|---------------|---------------|
| postgres | `postgres` | 5432 | `${POSTGRES_PORT:-5432}` |
| rag-api | `rag-api` | 8080 | `${RAG_API_PORT:-8080}` |
| mcp-server | `mcp-server` | 3000 | `${MCP_PORT:-3000}` |

All services on `rag-net` bridge network. External ports configurable via `.env`.

---

## 8. Makefile Targets

```makefile
# Makefile
.PHONY: up down build logs seed test lint shell db-shell

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
seed:                            ## Run initial source ingestion
	docker compose exec rag-api python scripts/seed_initial_sources.py

shell:                           ## Open shell in API container
	docker compose exec rag-api bash

db-shell:                        ## Open psql in database
	docker compose exec postgres psql -U $${POSTGRES_USER:-rag_user} -d $${POSTGRES_DB:-odyssey_rag}

# ── Testing ───────────────────────────────────────
test:                            ## Run tests inside container
	docker compose run --rm -e ENVIRONMENT=test rag-api pytest tests/ -v

test-unit:                       ## Run unit tests only
	docker compose run --rm -e ENVIRONMENT=test rag-api pytest tests/unit/ -v

lint:                            ## Run ruff linter
	docker compose run --rm rag-api ruff check src/ tests/

format:                          ## Auto-format code
	docker compose run --rm rag-api ruff format src/ tests/

# ── Database ──────────────────────────────────────
db-migrate:                      ## Run pending migrations
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
```

---

## 9. VS Code MCP Integration

### 9.1 HTTP/SSE Mode (team/centralized)

```json
// .vscode/mcp.json
{
  "servers": {
    "odyssey-rag": {
      "type": "sse",
      "url": "http://localhost:3000/sse",
      "headers": {}
    }
  }
}
```

### 9.2 stdio Mode (local dev)

```json
// .vscode/mcp.json
{
  "servers": {
    "odyssey-rag": {
      "type": "stdio",
      "command": "docker",
      "args": [
        "compose", "run", "--rm",
        "-e", "MCP_TRANSPORT=stdio",
        "mcp-server"
      ]
    }
  }
}
```

---

## 10. Startup Sequence

```bash
# 1. Clone and configure
git clone git@github.com:cbeltran-dev-blossom/RAG-odyssey-2026.git
cd RAG-odyssey-2026
cp .env.example .env
# Edit .env: set POSTGRES_PASSWORD and API keys

# 2. Build and start
make build
make up

# 3. Verify services
docker compose ps           # All 3 services "healthy"
curl http://localhost:8080/health   # {"status": "ok"}
curl http://localhost:3000/health   # {"status": "ok"}

# 4. Seed initial documents
make seed

# 5. Test MCP from VS Code
# Open VS Code → Configure .vscode/mcp.json → Use MCP tools
```

---

## 11. Resource Requirements

| Service | RAM (min) | RAM (recommended) | CPU | Disk |
|---------|-----------|-------------------|-----|------|
| postgres | 256 MB | 512 MB | 0.5 | 1 GB |
| rag-api | 1 GB | 2 GB | 1.0 | 3 GB (models) |
| mcp-server | 128 MB | 256 MB | 0.25 | - |
| **Total** | **~1.5 GB** | **~3 GB** | **1.75** | **~4 GB** |

Note: rag-api needs RAM for embedding model (~400MB) and reranker (~90MB) loaded in memory.
