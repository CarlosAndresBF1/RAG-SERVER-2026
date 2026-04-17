"""Unit tests for embedding providers.

Embedding models are mocked so tests run without GPU/network access.
"""

from __future__ import annotations

import sys
from types import ModuleType
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def _mock_openai_module() -> tuple[MagicMock, MagicMock]:
    """Return (mock_module, mock_AsyncOpenAI_class) with openai injected in sys.modules."""
    mock_openai = MagicMock(spec=ModuleType)
    mock_client_cls = MagicMock()
    mock_openai.AsyncOpenAI = mock_client_cls
    return mock_openai, mock_client_cls

from odyssey_rag.embeddings.factory import create_embedding_provider
from odyssey_rag.embeddings.nomic import NOMIC_EMBEDDING_DIM, NomicEmbeddingProvider
from odyssey_rag.embeddings.openai_provider import (
    OPENAI_EMBEDDING_DIM,
    OpenAIEmbeddingProvider,
)
from odyssey_rag.exceptions import ConfigError, EmbeddingError


# ── NomicEmbeddingProvider tests ──────────────────────────────────────────────


def _make_nomic_with_mock_model(fake_vectors: list[list[float]]) -> NomicEmbeddingProvider:
    """Return a NomicEmbeddingProvider whose _model is pre-injected via __dict__."""

    # Ensure sentence_transformers is mocked so the cached_property body never runs
    mock_st = MagicMock()

    import numpy as np

    mock_model = MagicMock()
    mock_model.encode = MagicMock(return_value=np.array(fake_vectors))

    provider = NomicEmbeddingProvider()
    # Inject directly into instance __dict__ to bypass cached_property
    provider.__dict__["_model"] = mock_model  # type: ignore[assignment]
    return provider


class TestNomicEmbeddingProvider:
    """Tests for the local nomic-embed-text provider."""

    @pytest.mark.asyncio
    async def test_embed_returns_correct_shape(self) -> None:
        """embed() returns one vector per input text."""
        fake_vectors = [[0.1] * NOMIC_EMBEDDING_DIM, [0.2] * NOMIC_EMBEDDING_DIM]
        provider = _make_nomic_with_mock_model(fake_vectors)

        result = await provider.embed(["hello", "world"])

        assert len(result) == 2
        assert len(result[0]) == NOMIC_EMBEDDING_DIM
        assert len(result[1]) == NOMIC_EMBEDDING_DIM

    @pytest.mark.asyncio
    async def test_embed_empty_input_returns_empty_list(self) -> None:
        """embed([]) returns [] without calling the model."""
        provider = NomicEmbeddingProvider()
        result = await provider.embed([])
        assert result == []

    @pytest.mark.asyncio
    async def test_embed_single_text(self) -> None:
        """embed() handles a single-element list."""
        fake_vector = [[0.5] * NOMIC_EMBEDDING_DIM]
        provider = _make_nomic_with_mock_model(fake_vector)

        result = await provider.embed(["only one"])

        assert len(result) == 1
        assert len(result[0]) == NOMIC_EMBEDDING_DIM

    @pytest.mark.asyncio
    async def test_embed_raises_embedding_error_on_model_failure(self) -> None:
        """embed() wraps unexpected exceptions in EmbeddingError."""

        provider = NomicEmbeddingProvider()
        mock_model = MagicMock()
        mock_model.encode = MagicMock(side_effect=RuntimeError("CUDA OOM"))
        provider.__dict__["_model"] = mock_model  # type: ignore[assignment]

        with pytest.raises(EmbeddingError, match="Embedding generation failed"):
            await provider.embed(["test"])

    def test_dimension_returns_768(self) -> None:
        """dimension() always returns 768."""
        provider = NomicEmbeddingProvider()
        assert provider.dimension() == NOMIC_EMBEDDING_DIM

    def test_model_loading_error_raises_embedding_error(self) -> None:
        """Model load failure raises EmbeddingError (not generic exception)."""
        provider = NomicEmbeddingProvider(model_name="nonexistent-model")

        with patch("builtins.__import__", side_effect=ImportError("no module")):
            # The _model cached_property triggers the load
            with pytest.raises(EmbeddingError):
                _ = provider._model  # noqa: SLF001 — testing internals


# ── OpenAIEmbeddingProvider tests ─────────────────────────────────────────────


class TestOpenAIEmbeddingProvider:
    """Tests for the OpenAI text-embedding-3-small provider."""

    @pytest.mark.asyncio
    async def test_embed_returns_correct_shape(self) -> None:
        """embed() returns one 768-dim vector per input text."""
        provider = OpenAIEmbeddingProvider(api_key="test-key")
        fake_embeddings = [[0.1] * OPENAI_EMBEDDING_DIM, [0.2] * OPENAI_EMBEDDING_DIM]

        mock_embedding_data = [MagicMock(embedding=v) for v in fake_embeddings]
        mock_response = MagicMock(data=mock_embedding_data)

        mock_openai, mock_client_cls = _mock_openai_module()
        mock_client = MagicMock()
        mock_client.embeddings.create = AsyncMock(return_value=mock_response)
        mock_client_cls.return_value = mock_client

        with patch.dict(sys.modules, {"openai": mock_openai}):
            result = await provider.embed(["foo", "bar"])

        assert len(result) == 2
        assert len(result[0]) == OPENAI_EMBEDDING_DIM

    @pytest.mark.asyncio
    async def test_embed_empty_input_returns_empty_list(self) -> None:
        """embed([]) returns [] without making an API call."""
        provider = OpenAIEmbeddingProvider(api_key="test-key")
        result = await provider.embed([])
        assert result == []

    @pytest.mark.asyncio
    async def test_embed_raises_embedding_error_on_api_failure(self) -> None:
        """embed() wraps API errors in EmbeddingError."""
        provider = OpenAIEmbeddingProvider(api_key="bad-key")

        mock_openai, mock_client_cls = _mock_openai_module()
        mock_client = MagicMock()
        mock_client.embeddings.create = AsyncMock(
            side_effect=Exception("401 Unauthorized")
        )
        mock_client_cls.return_value = mock_client

        with patch.dict(sys.modules, {"openai": mock_openai}):
            with pytest.raises(EmbeddingError, match="OpenAI embedding failed"):
                await provider.embed(["text"])

    def test_dimension_returns_768(self) -> None:
        """dimension() returns 768 matching nomic-embed dimensions."""
        provider = OpenAIEmbeddingProvider(api_key="test-key")
        assert provider.dimension() == OPENAI_EMBEDDING_DIM


# ── Factory tests ─────────────────────────────────────────────────────────────


class TestEmbeddingFactory:
    """Tests for create_embedding_provider() factory."""

    def test_factory_returns_nomic_provider_by_default(self) -> None:
        """nomic-local provider is created when embedding_provider='nomic-local'."""
        from odyssey_rag.config import Settings
        from odyssey_rag.embeddings.nomic import NomicEmbeddingProvider

        settings = Settings(embedding_provider="nomic-local")
        provider = create_embedding_provider(settings)
        assert isinstance(provider, NomicEmbeddingProvider)

    def test_factory_returns_openai_provider(self) -> None:
        """openai provider is created when embedding_provider='openai'."""
        from odyssey_rag.config import Settings

        settings = Settings(embedding_provider="openai", openai_api_key="sk-test")
        provider = create_embedding_provider(settings)
        assert isinstance(provider, OpenAIEmbeddingProvider)

    def test_factory_raises_config_error_for_unknown_provider(self) -> None:
        """Unknown provider name raises ConfigError."""
        from odyssey_rag.config import Settings
        from odyssey_rag.embeddings.factory import reset_embedding_provider_cache

        reset_embedding_provider_cache()
        settings = Settings(embedding_provider="cohere")
        with pytest.raises(ConfigError, match="Unknown EMBEDDING_PROVIDER"):
            create_embedding_provider(settings)

    def test_factory_raises_config_error_when_openai_key_missing(self) -> None:
        """OpenAI provider without API key raises ConfigError."""
        from odyssey_rag.config import Settings
        from odyssey_rag.embeddings.factory import reset_embedding_provider_cache

        reset_embedding_provider_cache()
        settings = Settings(embedding_provider="openai", openai_api_key="")
        with pytest.raises(ConfigError, match="OPENAI_API_KEY"):
            create_embedding_provider(settings)
