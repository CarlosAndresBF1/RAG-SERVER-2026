"""Abstract embedding provider interface.

All embedding providers implement BaseEmbeddingProvider so the rest of
the system remains decoupled from the underlying inference backend.
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class BaseEmbeddingProvider(ABC):
    """Abstract base class for all embedding providers.

    Concrete implementations include:
    - NomicEmbeddingProvider  (local, sentence-transformers)
    - OpenAIEmbeddingProvider (cloud, text-embedding-3-small)
    """

    @abstractmethod
    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for a list of texts.

        Args:
            texts: List of text strings to embed. May be empty.

        Returns:
            List of float vectors, one per input text. Empty list if
            texts is empty.

        Raises:
            EmbeddingError: If embedding generation fails.
        """

    @abstractmethod
    def dimension(self) -> int:
        """Return the dimensionality of vectors produced by this provider.

        Returns:
            Integer embedding dimension (e.g. 768 for nomic-embed-text).
        """
