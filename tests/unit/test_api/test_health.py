"""Tests for the /health endpoint."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient


@pytest.fixture()
def app():
    """Create a fresh FastAPI app for each test."""
    # Patch heavy imports before app creation
    with (
        patch("odyssey_rag.api.main.get_engine"),
        patch("odyssey_rag.api.main.close_engine", new_callable=AsyncMock),
    ):
        from odyssey_rag.api.main import create_app

        yield create_app()


@pytest.fixture()
async def client(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


class TestHealthEndpoint:
    """Tests for GET /health."""

    async def test_health_ok(self, client: AsyncClient) -> None:
        """Health returns 200 when all services are healthy."""
        mock_session = AsyncMock()
        mock_session.execute = AsyncMock()
        inner = MagicMock(
            __aenter__=AsyncMock(return_value=mock_session),
            __aexit__=AsyncMock(),
        )
        mock_factory = MagicMock(return_value=inner)

        with (
            patch("odyssey_rag.db.session.get_session_factory", return_value=mock_factory),
            patch("odyssey_rag.embeddings.factory.create_embedding_provider"),
            patch("odyssey_rag.api.deps.get_retrieval_engine"),
        ):
            resp = await client.get("/health")

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert "version" in data
        assert "services" in data

    async def test_health_degraded_when_db_fails(self, client: AsyncClient) -> None:
        """Health returns 503 when the database is unreachable."""
        mock_factory = MagicMock()
        ctx = MagicMock()
        ctx.__aenter__ = AsyncMock(side_effect=ConnectionError("db down"))
        ctx.__aexit__ = AsyncMock()
        mock_factory.return_value = ctx

        with (
            patch("odyssey_rag.db.session.get_session_factory", return_value=mock_factory),
            patch("odyssey_rag.embeddings.factory.create_embedding_provider"),
            patch("odyssey_rag.api.deps.get_retrieval_engine"),
        ):
            resp = await client.get("/health")

        assert resp.status_code == 503
        data = resp.json()
        assert data["status"] == "degraded"
        assert data["services"]["database"] == "error"

    async def test_health_degraded_when_embedding_fails(self, client: AsyncClient) -> None:
        """Health returns 503 when the embedding provider is unavailable."""
        mock_session = AsyncMock()
        mock_session.execute = AsyncMock()
        inner = MagicMock(
            __aenter__=AsyncMock(return_value=mock_session),
            __aexit__=AsyncMock(),
        )
        mock_factory = MagicMock(return_value=inner)

        embed_patch = patch(
            "odyssey_rag.embeddings.factory.create_embedding_provider",
            side_effect=RuntimeError("model missing"),
        )
        with (
            patch("odyssey_rag.db.session.get_session_factory", return_value=mock_factory),
            embed_patch,
            patch("odyssey_rag.api.deps.get_retrieval_engine"),
        ):
            resp = await client.get("/health")

        assert resp.status_code == 503
        data = resp.json()
        assert data["status"] == "degraded"
        assert data["services"]["embedding_model"] == "error"
