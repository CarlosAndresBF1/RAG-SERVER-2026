"""Tests for document/source CRUD API routes.

Covers:
    GET    /api/v1/sources
    GET    /api/v1/sources/{document_id}
    DELETE /api/v1/sources/{document_id}
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from odyssey_rag.db.models import Chunk, Document

# ── Helpers ───────────────────────────────────────────────────────────────────


def _make_doc(**overrides) -> Document:
    defaults = {
        "id": uuid.uuid4(),
        "source_path": "/data/spec.md",
        "source_type": "annex_b_spec",
        "file_hash": "abc123",
        "total_chunks": 3,
        "is_current": True,
        "created_at": datetime(2025, 1, 1, tzinfo=timezone.utc),  # noqa: UP017
        "updated_at": datetime(2025, 1, 1, tzinfo=timezone.utc),  # noqa: UP017
    }
    defaults.update(overrides)
    doc = MagicMock(spec=Document)
    for k, v in defaults.items():
        setattr(doc, k, v)
    return doc


def _make_chunk(**overrides) -> Chunk:
    defaults = {
        "id": uuid.uuid4(),
        "chunk_index": 0,
        "content": "Test chunk content",
        "token_count": 10,
        "section": "Introduction",
        "subsection": None,
        "metadata_json": {},
    }
    defaults.update(overrides)
    chunk = MagicMock(spec=Chunk)
    for k, v in defaults.items():
        setattr(chunk, k, v)
    return chunk


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


class TestListSources:
    """Tests for GET /api/v1/sources."""

    async def test_list_sources_returns_items(self, client: AsyncClient, app) -> None:
        doc = _make_doc()
        mock_session = AsyncMock()

        async def mock_get_session():
            yield mock_session

        with (
            patch("odyssey_rag.api.routes.sources.DocumentRepository") as mock_doc_repo,
        ):
            mock_repo = mock_doc_repo.return_value
            mock_repo.list_current = AsyncMock(return_value=[doc])
            mock_repo.count_current = AsyncMock(return_value=1)

            app.dependency_overrides[
                __import__("odyssey_rag.api.deps", fromlist=["get_async_session"]).get_async_session
            ] = mock_get_session

            resp = await client.get("/api/v1/sources")

        app.dependency_overrides.clear()
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert len(data["items"]) == 1
        assert data["items"][0]["source_path"] == "/data/spec.md"

    async def test_list_sources_empty(self, client: AsyncClient, app) -> None:
        mock_session = AsyncMock()

        async def mock_get_session():
            yield mock_session

        with patch("odyssey_rag.api.routes.sources.DocumentRepository") as mock_doc_repo:
            mock_repo = mock_doc_repo.return_value
            mock_repo.list_current = AsyncMock(return_value=[])
            mock_repo.count_current = AsyncMock(return_value=0)

            app.dependency_overrides[
                __import__("odyssey_rag.api.deps", fromlist=["get_async_session"]).get_async_session
            ] = mock_get_session

            resp = await client.get("/api/v1/sources")

        app.dependency_overrides.clear()
        assert resp.status_code == 200
        assert resp.json()["total"] == 0


class TestGetSource:
    """Tests for GET /api/v1/sources/{document_id}."""

    async def test_get_source_found(self, client: AsyncClient, app) -> None:
        doc = _make_doc()
        chunk = _make_chunk()
        mock_session = AsyncMock()

        async def mock_get_session():
            yield mock_session

        with (
            patch("odyssey_rag.api.routes.sources.DocumentRepository") as mock_doc_repo,
            patch("odyssey_rag.api.routes.sources.ChunkRepository") as mock_chunk_repo,
        ):
            mock_doc_repo.return_value.get_by_id = AsyncMock(return_value=doc)
            mock_chunk_repo.return_value.list_by_document = AsyncMock(return_value=[chunk])

            app.dependency_overrides[
                __import__("odyssey_rag.api.deps", fromlist=["get_async_session"]).get_async_session
            ] = mock_get_session

            resp = await client.get(f"/api/v1/sources/{doc.id}")

        app.dependency_overrides.clear()
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == str(doc.id)
        assert len(data["chunks"]) == 1

    async def test_get_source_not_found(self, client: AsyncClient, app) -> None:
        mock_session = AsyncMock()

        async def mock_get_session():
            yield mock_session

        with patch("odyssey_rag.api.routes.sources.DocumentRepository") as mock_doc_repo:
            mock_doc_repo.return_value.get_by_id = AsyncMock(return_value=None)

            app.dependency_overrides[
                __import__("odyssey_rag.api.deps", fromlist=["get_async_session"]).get_async_session
            ] = mock_get_session

            resp = await client.get(f"/api/v1/sources/{uuid.uuid4()}")

        app.dependency_overrides.clear()
        assert resp.status_code == 404

    async def test_get_source_bad_uuid(self, client: AsyncClient, app) -> None:
        mock_session = AsyncMock()

        async def mock_get_session():
            yield mock_session

        app.dependency_overrides[
            __import__("odyssey_rag.api.deps", fromlist=["get_async_session"]).get_async_session
        ] = mock_get_session

        resp = await client.get("/api/v1/sources/not-a-uuid")

        app.dependency_overrides.clear()
        assert resp.status_code == 400


class TestDeleteSource:
    """Tests for DELETE /api/v1/sources/{document_id}."""

    async def test_delete_source_success(self, client: AsyncClient, app) -> None:
        doc = _make_doc()
        mock_session = AsyncMock()

        async def mock_get_session():
            yield mock_session

        with (
            patch("odyssey_rag.api.routes.sources.DocumentRepository") as mock_doc_repo,
            patch("odyssey_rag.api.routes.sources.ChunkRepository") as mock_chunk_repo,
        ):
            mock_doc_repo.return_value.get_by_id = AsyncMock(return_value=doc)
            mock_doc_repo.return_value.delete = AsyncMock(return_value=True)
            mock_chunk_repo.return_value.count_by_document = AsyncMock(return_value=3)

            app.dependency_overrides[
                __import__("odyssey_rag.api.deps", fromlist=["get_async_session"]).get_async_session
            ] = mock_get_session

            resp = await client.delete(f"/api/v1/sources/{doc.id}")

        app.dependency_overrides.clear()
        assert resp.status_code == 200
        data = resp.json()
        assert data["deleted"] is True
        assert data["chunks_deleted"] == 3

    async def test_delete_source_not_found(self, client: AsyncClient, app) -> None:
        mock_session = AsyncMock()

        async def mock_get_session():
            yield mock_session

        with patch("odyssey_rag.api.routes.sources.DocumentRepository") as mock_doc_repo:
            mock_doc_repo.return_value.get_by_id = AsyncMock(return_value=None)

            app.dependency_overrides[
                __import__("odyssey_rag.api.deps", fromlist=["get_async_session"]).get_async_session
            ] = mock_get_session

            resp = await client.delete(f"/api/v1/sources/{uuid.uuid4()}")

        app.dependency_overrides.clear()
        assert resp.status_code == 404
