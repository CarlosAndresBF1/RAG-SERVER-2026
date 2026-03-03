"""nomic-embed-text local embedding provider using sentence-transformers.

Runs entirely in-container — no external API calls, zero per-token cost.
Model is lazy-loaded on first use and cached for subsequent calls.
"""

from __future__ import annotations

import asyncio
from functools import cached_property
from typing import TYPE_CHECKING

import structlog

from odyssey_rag.embeddings.provider import BaseEmbeddingProvider
from odyssey_rag.exceptions import EmbeddingError

if TYPE_CHECKING:
    pass

logger = structlog.get_logger(__name__)

NOMIC_EMBEDDING_DIM: int = 768
DEFAULT_MODEL_NAME: str = "nomic-ai/nomic-embed-text-v1.5"


class NomicEmbeddingProvider(BaseEmbeddingProvider):
    """Local embedding provider using nomic-embed-text via sentence-transformers.

    Uses asyncio's thread-pool executor to run the synchronous
    sentence-transformers encode() without blocking the event loop.

    Attributes:
        _model_name: HuggingFace model identifier.
    """

    def __init__(self, model_name: str = DEFAULT_MODEL_NAME) -> None:
        """Initialize the nomic embedding provider.

        Args:
            model_name: HuggingFace model path for nomic-embed-text.
        """
        self._model_name = model_name

    @cached_property
    def _model(self) -> object:
        """Lazy-load the sentence-transformers model (cached after first call).

        Returns:
            Loaded SentenceTransformer model instance.

        Raises:
            EmbeddingError: If the model fails to load.
        """
        try:
            from sentence_transformers import SentenceTransformer  # type: ignore[import-untyped]

            logger.info("embedding.model_loading", model=self._model_name)
            model = SentenceTransformer(self._model_name, trust_remote_code=True)
            logger.info("embedding.model_loaded", model=self._model_name)
            return model  # type: ignore[no-any-return]
        except EmbeddingError:
            raise
        except Exception as exc:
            msg = f"Failed to load embedding model '{self._model_name}': {exc}"
            raise EmbeddingError(msg) from exc

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings using nomic-embed-text.

        Runs the synchronous encode() call in a thread-pool executor to
        avoid blocking the asyncio event loop.

        Args:
            texts: List of text strings to embed. Returns [] if empty.

        Returns:
            List of 768-dimensional float vectors, one per input text.

        Raises:
            EmbeddingError: If embedding generation fails.
        """
        if not texts:
            return []

        try:
            loop = asyncio.get_running_loop()
            model = self._model

            def _encode() -> list[list[float]]:
                import numpy as np  # type: ignore[import-untyped]

                result = model.encode(  # type: ignore[attr-defined]
                    texts,
                    normalize_embeddings=True,
                    show_progress_bar=False,
                )
                if isinstance(result, np.ndarray):
                    return result.tolist()
                return list(result)

            embeddings: list[list[float]] = await loop.run_in_executor(None, _encode)
            return embeddings
        except EmbeddingError:
            raise
        except Exception as exc:
            msg = f"Embedding generation failed for {len(texts)} texts: {exc}"
            raise EmbeddingError(msg) from exc

    def dimension(self) -> int:
        """Return the embedding dimensionality.

        Returns:
            768 (nomic-embed-text-v1.5 output dimension).
        """
        return NOMIC_EMBEDDING_DIM
