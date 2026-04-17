"""Centralized configuration management using pydantic-settings.

All configuration is loaded from environment variables (12-factor app).
See .env.example for documentation of all available options.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic import field_validator
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
    llm_provider: str = "openai"  # openai | anthropic | gemini | ollama
    openai_api_key: str = ""
    anthropic_api_key: str = ""
    google_api_key: str = ""
    ollama_base_url: str = "http://host.docker.internal:11434"
    ollama_model: str = "llama3.1:latest"

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

    # ── Cache ─────────────────────────────────
    cache_ttl: int = 300  # seconds (5 min)
    cache_max_size: int = 256
    cache_enabled: bool = True

    # ── Job resilience ────────────────────────
    job_timeout_minutes: int = 30  # mark running jobs as failed after this
    job_watchdog_interval: int = 60  # seconds between watchdog sweeps

    # ── Auth ──────────────────────────────────
    # Comma-separated list of valid API keys, e.g. "key-abc123,key-def456"
    api_keys: list[str] = []

    @field_validator("api_keys", mode="before")
    @classmethod
    def parse_api_keys(cls, v: object) -> list[str]:
        if isinstance(v, str):
            return [k.strip() for k in v.split(",") if k.strip()]
        if isinstance(v, (list, tuple)):
            return [str(k).strip() for k in v if str(k).strip()]
        return []

    model_config = {
        "env_file": ".env",
        "case_sensitive": False,
        "extra": "ignore",
        "env_ignore_empty": True,
    }


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Get cached application settings singleton.

    Returns:
        Settings instance loaded from environment variables.
    """
    return Settings()
