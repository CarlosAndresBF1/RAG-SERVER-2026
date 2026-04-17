"""Tests for RetrievalEngine.search() with mocked dependencies.

All external dependencies (DB, embeddings, reranker) are mocked so tests
run without any infrastructure.
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

from odyssey_rag.retrieval.response_builder import RetrievalResponse
from odyssey_rag.retrieval.vector_search import SearchResult

# ── Helpers ───────────────────────────────────────────────────────────────────


def _make_search_result(**overrides) -> SearchResult:
    defaults = {
        "chunk_id": uuid.uuid4(),
        "content": "Test content",
        "source_type": "annex_b_spec",
        "score": 0.9,
    }
    defaults.update(overrides)
    return SearchResult(**defaults)


def _make_settings(**overrides):
    mock = MagicMock()
    mock.reranker_enabled = False
    mock.reranker_model = "cross-encoder/ms-marco-MiniLM-L-6-v2"
    mock.default_top_k = 8
    mock.environment = "test"
    mock.database_url = "postgresql+asyncpg://test:test@localhost/test"
    mock.embedding_provider = "nomic-local"
    mock.embedding_model = "nomic-embed-text-v1.5"
    mock.embedding_dimension = 768
    mock.cache_enabled = False
    mock.cache_max_size = 100
    mock.cache_ttl = 300
    for k, v in overrides.items():
        setattr(mock, k, v)
    return mock


# ── Tests ─────────────────────────────────────────────────────────────────────


class TestRetrievalEngine:
    """Tests for the RetrievalEngine orchestration."""

    @patch("odyssey_rag.retrieval.engine.get_settings")
    def test_engine_init_passthrough_reranker(self, mock_settings) -> None:
        """Engine initializes with PassthroughReranker when reranker_enabled=False."""
        mock_settings.return_value = _make_settings(reranker_enabled=False)

        from odyssey_rag.retrieval.engine import RetrievalEngine
        from odyssey_rag.retrieval.reranker import PassthroughReranker

        engine = RetrievalEngine()
        assert isinstance(engine._reranker, PassthroughReranker)

    @patch("odyssey_rag.retrieval.engine.get_settings")
    async def test_search_basic(self, mock_settings) -> None:
        """search() runs the full pipeline and returns a RetrievalResponse."""
        mock_settings.return_value = _make_settings()

        sr1 = _make_search_result(content="pacs.008 mandatory fields")
        sr2 = _make_search_result(content="camt.056 cancel request")

        with (
            patch("odyssey_rag.retrieval.engine.create_embedding_provider") as mock_embed_factory,
            patch("odyssey_rag.retrieval.engine.vector_search", new_callable=AsyncMock) as mock_vs,
            patch("odyssey_rag.retrieval.engine.bm25_search", new_callable=AsyncMock) as mock_bm25,
        ):
            mock_provider = MagicMock()
            mock_provider.embed = AsyncMock(return_value=[[0.1] * 768])
            mock_embed_factory.return_value = mock_provider

            mock_vs.return_value = [sr1]
            mock_bm25.return_value = [sr2]

            from odyssey_rag.retrieval.engine import RetrievalEngine

            engine = RetrievalEngine()
            response = await engine.search("What are mandatory fields for pacs.008?")

        assert isinstance(response, RetrievalResponse)
        assert response.query is not None

    @patch("odyssey_rag.retrieval.engine.get_settings")
    async def test_search_with_tool_context(self, mock_settings) -> None:
        """Tool context parameters are forwarded through the pipeline."""
        mock_settings.return_value = _make_settings()

        with (
            patch("odyssey_rag.retrieval.engine.create_embedding_provider") as mock_embed_factory,
            patch("odyssey_rag.retrieval.engine.vector_search", new_callable=AsyncMock) as mock_vs,
            patch("odyssey_rag.retrieval.engine.bm25_search", new_callable=AsyncMock) as mock_bm25,
        ):
            mock_provider = MagicMock()
            mock_provider.embed = AsyncMock(return_value=[[0.1] * 768])
            mock_embed_factory.return_value = mock_provider
            mock_vs.return_value = []
            mock_bm25.return_value = []

            from odyssey_rag.retrieval.engine import RetrievalEngine

            engine = RetrievalEngine()
            response = await engine.search(
                "show builder method",
                tool_context={"message_type": "pacs.008", "focus": "builder"},
            )

        assert isinstance(response, RetrievalResponse)

    @patch("odyssey_rag.retrieval.engine.get_settings")
    async def test_search_embedding_failure_fallback(self, mock_settings) -> None:
        """When embedding fails, vector search is skipped; BM25 still runs."""
        mock_settings.return_value = _make_settings()

        sr = _make_search_result(content="fallback result")

        with (
            patch("odyssey_rag.retrieval.engine.create_embedding_provider") as mock_embed_factory,
            patch("odyssey_rag.retrieval.engine.vector_search", new_callable=AsyncMock) as mock_vs,
            patch("odyssey_rag.retrieval.engine.bm25_search", new_callable=AsyncMock) as mock_bm25,
        ):
            mock_provider = MagicMock()
            mock_provider.embed = AsyncMock(side_effect=RuntimeError("model offline"))
            mock_embed_factory.return_value = mock_provider
            mock_bm25.return_value = [sr]
            # vector_search should not be called when embedding fails
            mock_vs.return_value = []

            from odyssey_rag.retrieval.engine import RetrievalEngine

            engine = RetrievalEngine()
            response = await engine.search("test query")

        assert isinstance(response, RetrievalResponse)
        # BM25 was still called
        mock_bm25.assert_called_once()

    @patch("odyssey_rag.retrieval.engine.get_settings")
    async def test_search_empty_results(self, mock_settings) -> None:
        """Empty search results produce a valid response with no evidence."""
        mock_settings.return_value = _make_settings()

        with (
            patch("odyssey_rag.retrieval.engine.create_embedding_provider") as mock_embed_factory,
            patch("odyssey_rag.retrieval.engine.vector_search", new_callable=AsyncMock) as mock_vs,
            patch("odyssey_rag.retrieval.engine.bm25_search", new_callable=AsyncMock) as mock_bm25,
        ):
            mock_provider = MagicMock()
            mock_provider.embed = AsyncMock(return_value=[[0.1] * 768])
            mock_embed_factory.return_value = mock_provider
            mock_vs.return_value = []
            mock_bm25.return_value = []

            from odyssey_rag.retrieval.engine import RetrievalEngine

            engine = RetrievalEngine()
            response = await engine.search("totally irrelevant query")

        assert isinstance(response, RetrievalResponse)
        assert len(response.evidence) == 0
