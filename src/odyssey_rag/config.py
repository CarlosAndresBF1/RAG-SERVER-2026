"""Centralized configuration management using pydantic-settings.

All configuration is loaded from environment variables (12-factor app).
See .env.example for documentation of all available options.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # ── Database ──────────────────────────────
    database_url: str = "postgresql+asyncpg://rag_user:changeme@localhost:5432/odyssey_rag"

    # ── Embeddings ────────────────────────────
    embedding_provider: str = "nomic-local"  # nomic-local | openai | cohere
    embedding_model: str = "nomic-embed-text-v1.5"
    embedding_dimension: int = 768

    # ── LLM ───────────────────────────────────
    llm_provider: str = "openai"  # openai | anthropic | gemini
    openai_api_key: str = ""
    anthropic_api_key: str = ""
    google_api_key: str = ""

    # ── MCP ───────────────────────────────────
    mcp_api_key: str = ""
    mcp_transport: str = "http"  # stdio | http
    mcp_port: int = 3000

    # ── Search ────────────────────────────────
    default_top_k: int = 8
    reranker_enabled: bool = True
    reranker_model: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"

    # ── Ingestion ─────────────────────────────
    chunk_size: int = 512  # tokens
    chunk_overlap: int = 64  # tokens

    # ── Application ───────────────────────────
    environment: str = "development"  # development | staging | production
    log_level: str = "info"
    rag_api_url: str = "http://localhost:8080"

    model_config = {
        "env_file": ".env",
        "case_sensitive": False,
        "extra": "ignore",
    }


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Get cached application settings singleton.

    Returns:
        Settings instance loaded from environment variables.
    """
    return Settings()
