"""OpenAI embedding provider using text-embedding-3-small.

Fallback provider when nomic-embed-text is unavailable (e.g. low-memory
environments). Requires OPENAI_API_KEY environment variable.
"""

from __future__ import annotations

import structlog

from odyssey_rag.embeddings.provider import BaseEmbeddingProvider
from odyssey_rag.exceptions import EmbeddingError

logger = structlog.get_logger(__name__)

OPENAI_EMBEDDING_DIM: int = 768  # text-embedding-3-small with dimensions=768
DEFAULT_MODEL: str = "text-embedding-3-small"


class OpenAIEmbeddingProvider(BaseEmbeddingProvider):
    """OpenAI embedding provider using text-embedding-3-small.

    Configured via OPENAI_API_KEY environment variable. Uses dimensions=768
    to match the nomic-embed-text output size for drop-in compatibility.

    Attributes:
        _api_key: OpenAI API key.
        _model: Model name to use.
    """

    def __init__(self, api_key: str, model: str = DEFAULT_MODEL) -> None:
        """Initialize the OpenAI embedding provider.

        Args:
            api_key: OpenAI API key (required).
            model: OpenAI model name for embeddings.
        """
        self._api_key = api_key
        self._model = model

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings using the OpenAI Embeddings API.

        Args:
            texts: List of text strings to embed. Returns [] if empty.

        Returns:
            List of 768-dimensional float vectors, one per input text.

        Raises:
            EmbeddingError: If the API call fails or returns an error.
        """
        if not texts:
            return []

        try:
            from openai import AsyncOpenAI  # type: ignore[import-untyped]

            client = AsyncOpenAI(api_key=self._api_key)
            response = await client.embeddings.create(
                model=self._model,
                input=texts,
                dimensions=OPENAI_EMBEDDING_DIM,
            )
            return [item.embedding for item in response.data]
        except Exception as exc:
            msg = f"OpenAI embedding failed for {len(texts)} texts: {exc}"
            raise EmbeddingError(msg) from exc

    def dimension(self) -> int:
        """Return the embedding dimensionality.

        Returns:
            768 (text-embedding-3-small with dimensions=768).
        """
        return OPENAI_EMBEDDING_DIM
