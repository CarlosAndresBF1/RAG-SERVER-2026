"""Tests for ingestion API routes.

Covers:
    POST /api/v1/ingest
    POST /api/v1/ingest/batch
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient


@pytest.fixture()
def app():
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


# ── Tests ─────────────────────────────────────────────────────────────────────


class TestIngestEndpoint:
    """Tests for POST /api/v1/ingest."""

    async def test_ingest_single_file(self, client: AsyncClient, app) -> None:
        """Ingest returns a pending job_id immediately."""
        mock_ctx = AsyncMock()
        mock_session = AsyncMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_session)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)

        with (
            patch("odyssey_rag.api.routes.ingest.detect_source_type", return_value="annex_b_spec"),
            patch("odyssey_rag.api.routes.ingest.db_session", return_value=mock_ctx),
            patch("odyssey_rag.api.routes.ingest.IngestJobRepository") as mock_repo_cls,
            patch("odyssey_rag.api.routes.ingest.asyncio") as mock_asyncio,
        ):
            mock_repo_cls.return_value.insert = AsyncMock()
            mock_asyncio.create_task = MagicMock()

            resp = await client.post(
                "/api/v1/ingest",
                json={"source_path": "/data/spec.md"},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "pending"
        assert "job_id" in data
        assert data["source_path"] == "/data/spec.md"
        assert data["source_type"] == "annex_b_spec"

    async def test_ingest_with_overrides(self, client: AsyncClient, app) -> None:
        mock_ctx = AsyncMock()
        mock_session = AsyncMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_session)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)

        with (
            patch("odyssey_rag.api.routes.ingest.detect_source_type", return_value="php_code"),
            patch("odyssey_rag.api.routes.ingest.db_session", return_value=mock_ctx),
            patch("odyssey_rag.api.routes.ingest.IngestJobRepository") as mock_repo_cls,
            patch("odyssey_rag.api.routes.ingest.asyncio") as mock_asyncio,
        ):
            mock_repo_cls.return_value.insert = AsyncMock()
            mock_asyncio.create_task = MagicMock()

            resp = await client.post(
                "/api/v1/ingest",
                json={
                    "source_path": "/src/Builder.php",
                    "source_type": "php_code",
                    "replace_existing": True,
                },
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["source_type"] == "php_code"

    async def test_ingest_missing_source_path(self, client: AsyncClient, app) -> None:
        """Empty source_path should fail validation."""
        resp = await client.post("/api/v1/ingest", json={"source_path": ""})
        assert resp.status_code == 422


class TestBatchIngestEndpoint:
    """Tests for POST /api/v1/ingest/batch."""

    async def test_batch_ingest(self, client: AsyncClient, app) -> None:
        mock_ctx = AsyncMock()
        mock_session = AsyncMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_session)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)

        with (
            patch("odyssey_rag.api.routes.ingest.detect_source_type", return_value="annex_b_spec"),
            patch("odyssey_rag.api.routes.ingest.db_session", return_value=mock_ctx),
            patch("odyssey_rag.api.routes.ingest.IngestJobRepository") as mock_repo_cls,
            patch("odyssey_rag.api.routes.ingest.asyncio") as mock_asyncio,
        ):
            mock_repo_cls.return_value.insert = AsyncMock()
            mock_asyncio.create_task = MagicMock()

            resp = await client.post(
                "/api/v1/ingest/batch",
                json={
                    "sources": [
                        {"source_path": "/data/spec1.md"},
                        {"source_path": "/data/spec2.md"},
                    ],
                    "replace_existing": False,
                },
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2
        assert len(data["jobs"]) == 2
        for job in data["jobs"]:
            assert job["status"] == "pending"

    async def test_batch_ingest_empty_sources(self, client: AsyncClient, app) -> None:
        """Batch with empty source list should succeed with total=0."""
        resp = await client.post(
            "/api/v1/ingest/batch",
            json={"sources": []},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0
