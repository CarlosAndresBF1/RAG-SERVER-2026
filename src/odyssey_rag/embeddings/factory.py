"""Embedding provider factory.

Selects and instantiates the configured embedding provider based on the
EMBEDDING_PROVIDER environment variable (settings.embedding_provider).

The provider instance is cached as a module-level singleton so that the
embedding model is loaded only once per process (important for the ~500 MB
nomic-embed-text model in CPU-only containers).
"""

from __future__ import annotations

from odyssey_rag.config import Settings
from odyssey_rag.embeddings.provider import BaseEmbeddingProvider
from odyssey_rag.exceptions import ConfigError

_cached_provider: BaseEmbeddingProvider | None = None
_cached_provider_key: str | None = None


def reset_embedding_provider_cache() -> None:
    """Clear the cached provider instance (used in tests)."""
    global _cached_provider, _cached_provider_key
    _cached_provider = None
    _cached_provider_key = None


def create_embedding_provider(settings: Settings) -> BaseEmbeddingProvider:
    """Create and return the configured embedding provider (singleton).

    Provider selection via settings.embedding_provider:
    - ``"nomic-local"`` (default): Local nomic-embed-text, no API key needed.
    - ``"openai"``: OpenAI text-embedding-3-small, requires OPENAI_API_KEY.

    The provider instance is cached per (provider_name, model) combination
    so the heavyweight model is loaded only once per worker process.

    Args:
        settings: Application settings instance.

    Returns:
        Configured and ready-to-use embedding provider instance.

    Raises:
        ConfigError: If the provider name is unknown or a required API key
            is missing.
    """
    global _cached_provider, _cached_provider_key

    provider_name = settings.embedding_provider.lower()
    cache_key = f"{provider_name}:{settings.embedding_model}"

    if _cached_provider is not None and _cached_provider_key == cache_key:
        return _cached_provider

    if provider_name == "nomic-local":
        from odyssey_rag.embeddings.nomic import NomicEmbeddingProvider

        _cached_provider = NomicEmbeddingProvider(model_name=settings.embedding_model)
        _cached_provider_key = cache_key
        return _cached_provider

    if provider_name == "openai":
        if not settings.openai_api_key:
            raise ConfigError(
                "OPENAI_API_KEY is required when EMBEDDING_PROVIDER=openai"
            )
        from odyssey_rag.embeddings.openai_provider import OpenAIEmbeddingProvider

        _cached_provider = OpenAIEmbeddingProvider(api_key=settings.openai_api_key)
        _cached_provider_key = cache_key
        return _cached_provider

    raise ConfigError(
        f"Unknown EMBEDDING_PROVIDER: '{provider_name}'. "
        "Valid options: nomic-local, openai"
    )
