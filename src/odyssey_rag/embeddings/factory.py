"""Embedding provider factory.

Selects and instantiates the configured embedding provider based on the
EMBEDDING_PROVIDER environment variable (settings.embedding_provider).
"""

from __future__ import annotations

from odyssey_rag.config import Settings
from odyssey_rag.embeddings.provider import BaseEmbeddingProvider
from odyssey_rag.exceptions import ConfigError


def create_embedding_provider(settings: Settings) -> BaseEmbeddingProvider:
    """Create and return the configured embedding provider.

    Provider selection via settings.embedding_provider:
    - ``"nomic-local"`` (default): Local nomic-embed-text, no API key needed.
    - ``"openai"``: OpenAI text-embedding-3-small, requires OPENAI_API_KEY.

    Args:
        settings: Application settings instance.

    Returns:
        Configured and ready-to-use embedding provider instance.

    Raises:
        ConfigError: If the provider name is unknown or a required API key
            is missing.
    """
    provider_name = settings.embedding_provider.lower()

    if provider_name == "nomic-local":
        from odyssey_rag.embeddings.nomic import NomicEmbeddingProvider

        return NomicEmbeddingProvider(model_name=settings.embedding_model)

    if provider_name == "openai":
        if not settings.openai_api_key:
            raise ConfigError(
                "OPENAI_API_KEY is required when EMBEDDING_PROVIDER=openai"
            )
        from odyssey_rag.embeddings.openai_provider import OpenAIEmbeddingProvider

        return OpenAIEmbeddingProvider(api_key=settings.openai_api_key)

    raise ConfigError(
        f"Unknown EMBEDDING_PROVIDER: '{provider_name}'. "
        "Valid options: nomic-local, openai"
    )
