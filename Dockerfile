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
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy source
COPY src/ ./src/
COPY scripts/ ./scripts/
COPY db/ ./db/

ENV PYTHONPATH=/app/src
ENV PYTHONUNBUFFERED=1

# ── Stage 2: RAG API ─────────────────────────────────
FROM base AS api

# Download embedding model on build (cached in layer)
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('nomic-ai/nomic-embed-text-v1.5', trust_remote_code=True)"
RUN python -c "from sentence_transformers import CrossEncoder; CrossEncoder('cross-encoder/ms-marco-MiniLM-L-6-v2')"

EXPOSE 8080

CMD ["uvicorn", "odyssey_rag.api.main:app", "--host", "0.0.0.0", "--port", "8080", "--workers", "2"]

# ── Stage 3: MCP Server ──────────────────────────────
FROM base AS mcp

EXPOSE 3000

CMD ["python", "-m", "odyssey_rag.mcp_server.main"]

# ── Stage 4: Dev (all tools) ─────────────────────────
FROM base AS dev

COPY requirements-dev.txt ./
RUN pip install --no-cache-dir -r requirements-dev.txt

# Download models
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('nomic-ai/nomic-embed-text-v1.5', trust_remote_code=True)"
RUN python -c "from sentence_transformers import CrossEncoder; CrossEncoder('cross-encoder/ms-marco-MiniLM-L-6-v2')"

CMD ["bash"]
