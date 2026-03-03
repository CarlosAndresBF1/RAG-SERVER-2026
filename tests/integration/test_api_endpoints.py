"""Integration tests for all API endpoints.

Uses FastAPI's TestClient with dependency overrides to avoid real DB/model
connections.  All external I/O (DB session, retrieval engine, ingest pipeline)
is mocked.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from odyssey_rag.api.auth import verify_api_key
from odyssey_rag.api.deps import get_async_session, get_retrieval_engine
from odyssey_rag.api.main import app

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_DOC_ID = uuid.uuid4()
_CHUNK_ID = uuid.uuid4()
_NOW = datetime.now(tz=timezone.utc)


def _make_doc(**kwargs: Any):
    """Return a MagicMock that looks like a Document ORM row."""
    doc = MagicMock()
    doc.id = kwargs.get("id", _DOC_ID)
    doc.source_path = kwargs.get("source_path", "md/test.md")
    doc.source_type = kwargs.get("source_type", "generic_text")
    doc.file_hash = kwargs.get("file_hash", "abc123")
    doc.total_chunks = kwargs.get("total_chunks", 5)
    doc.is_current = kwargs.get("is_current", True)
    doc.created_at = kwargs.get("created_at", _NOW)
    return doc


def _make_chunk(**kwargs: Any):
    """Return a MagicMock that looks like a Chunk ORM row."""
    chunk = MagicMock()
    chunk.id = kwargs.get("id", _CHUNK_ID)
    chunk.chunk_index = kwargs.get("chunk_index", 0)
    chunk.content = kwargs.get("content", "Some chunk text")
    chunk.token_count = kwargs.get("token_count", 42)
    chunk.section = kwargs.get("section", "intro")
    chunk.subsection = kwargs.get("subsection", None)
    chunk.metadata_json = kwargs.get("metadata_json", {})
    return chunk


def _make_retrieval_response(query: str = "test query"):
    """Return a MagicMock that looks like a RetrievalResponse."""
    resp = MagicMock()
    resp.query = query
    resp.gaps = []
    resp.followups = ["Find business rules"]

    citation = MagicMock()
    citation.source_path = "md/test.md"
    citation.section = "intro"
    citation.chunk_index = 0

    evidence = MagicMock()
    evidence.text = "Relevant chunk text"
    evidence.relevance = 0.85
    evidence.citations = [citation]
    evidence.message_type = "pacs.008"
    evidence.source_type = "annex_b_spec"

    resp.evidence = [evidence]
    return resp


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_session():
    """Async mock that stands in for an SQLAlchemy AsyncSession."""
    session = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    return session


@pytest.fixture
def mock_engine():
    """Mock RetrievalEngine with a canned search response."""
    engine = MagicMock()
    engine.search = AsyncMock(return_value=_make_retrieval_response())
    return engine


@pytest.fixture
def client(mock_session, mock_engine):
    """TestClient with all external dependencies overridden.

    Patches get_engine/close_engine so the lifespan hook doesn't attempt
    a real DB connection (asyncpg not installed in the local test env).
    """
    app.dependency_overrides[get_async_session] = lambda: mock_session
    app.dependency_overrides[get_retrieval_engine] = lambda: mock_engine
    app.dependency_overrides[verify_api_key] = lambda: "test-key"

    with (
        patch("odyssey_rag.api.main.get_engine"),
        patch("odyssey_rag.api.main.close_engine", new=AsyncMock()),
    ):
        with TestClient(app) as c:
            yield c

    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------


class TestHealth:
    def _mock_db_session(self):
        """Build a mock session factory that doesn't need asyncpg."""
        mock_sess = AsyncMock()
        mock_sess.execute = AsyncMock()
        mock_sess.__aenter__ = AsyncMock(return_value=mock_sess)
        mock_sess.__aexit__ = AsyncMock(return_value=False)
        mock_factory = MagicMock()
        mock_factory.return_value = mock_sess
        return mock_factory

    def test_health_ok(self, client: TestClient):
        """Health endpoint returns 200 when all services respond."""
        with (
            patch("odyssey_rag.db.session.get_session_factory", return_value=self._mock_db_session()),
            patch("odyssey_rag.embeddings.factory.create_embedding_provider"),
        ):
            resp = client.get("/health")

        assert resp.status_code == 200
        data = resp.json()
        assert data["version"] == "0.1.0"

    def test_health_has_services_key(self, client: TestClient):
        """Health response always contains a 'services' mapping."""
        with (
            patch("odyssey_rag.db.session.get_session_factory", return_value=self._mock_db_session()),
            patch("odyssey_rag.embeddings.factory.create_embedding_provider"),
        ):
            resp = client.get("/health")

        data = resp.json()
        assert "services" in data
        assert "database" in data["services"]
        assert "embedding_model" in data["services"]
        assert "reranker" in data["services"]


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------


class TestSearch:
    def test_search_returns_evidence(self, client: TestClient, mock_engine):
        """POST /search returns 200 with evidence list."""
        resp = client.post("/api/v1/search", json={"query": "pacs.008 group header"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["query"] == "test query"
        assert len(data["evidence"]) == 1
        assert data["evidence"][0]["relevance"] == 0.85
        assert "followups" in data
        assert "metadata" in data
        assert "search_time_ms" in data["metadata"]

    def test_search_passes_tool_context(self, client: TestClient, mock_engine):
        """message_type and focus are forwarded as tool_context."""
        resp = client.post(
            "/api/v1/search",
            json={
                "query": "credit transfer",
                "message_type": "pacs.008",
                "focus": "fields",
                "top_k": 5,
            },
        )
        assert resp.status_code == 200
        call_kwargs = mock_engine.search.call_args
        tool_ctx = call_kwargs.kwargs.get("tool_context") or call_kwargs[1].get("tool_context")
        assert tool_ctx is not None
        assert tool_ctx["message_type"] == "pacs.008"
        assert tool_ctx["focus"] == "fields"

    def test_search_empty_query_returns_422(self, client: TestClient):
        """Empty query string fails validation."""
        resp = client.post("/api/v1/search", json={"query": ""})
        assert resp.status_code == 422

    def test_search_invalid_message_type_returns_422(self, client: TestClient):
        """message_type not matching pattern fails validation."""
        resp = client.post(
            "/api/v1/search", json={"query": "test", "message_type": "invalid"}
        )
        assert resp.status_code == 422

    def test_search_invalid_focus_returns_422(self, client: TestClient):
        """focus not in allowed values fails validation."""
        resp = client.post(
            "/api/v1/search", json={"query": "test", "focus": "unknown"}
        )
        assert resp.status_code == 422

    def test_search_top_k_bounds(self, client: TestClient):
        """top_k must be between 1 and 20."""
        assert client.post("/api/v1/search", json={"query": "x", "top_k": 0}).status_code == 422
        assert client.post("/api/v1/search", json={"query": "x", "top_k": 21}).status_code == 422
        assert client.post("/api/v1/search", json={"query": "x", "top_k": 1}).status_code == 200

    def test_search_missing_query_returns_422(self, client: TestClient):
        """Missing required 'query' field fails validation."""
        resp = client.post("/api/v1/search", json={})
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Ingest
# ---------------------------------------------------------------------------


class TestIngest:
    def _mock_ingest_result(self, status: str = "completed"):
        result = MagicMock()
        result.status = status
        result.source_path = "/app/sources/test.md"
        result.source_type = "generic_text"
        result.chunks_created = 10 if status == "completed" else 0
        result.document_id = _DOC_ID if status == "completed" else None
        result.reason = "unchanged" if status == "skipped" else ""
        result.error = "Parse failed" if status == "failed" else ""
        return result

    def test_ingest_completed(self, client: TestClient):
        """Successful ingest returns status=completed with document_id."""
        with patch(
            "odyssey_rag.api.routes.ingest.ingest",
            AsyncMock(return_value=self._mock_ingest_result("completed")),
        ):
            resp = client.post(
                "/api/v1/ingest",
                json={"source_path": "/app/sources/test.md"},
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "completed"
        assert data["document_id"] == str(_DOC_ID)
        assert data["chunks_created"] == 10

    def test_ingest_skipped(self, client: TestClient):
        """Unchanged file returns status=skipped with reason."""
        with patch(
            "odyssey_rag.api.routes.ingest.ingest",
            AsyncMock(return_value=self._mock_ingest_result("skipped")),
        ):
            resp = client.post(
                "/api/v1/ingest",
                json={"source_path": "/app/sources/test.md"},
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "skipped"
        assert data["reason"] == "unchanged"

    def test_ingest_failed(self, client: TestClient):
        """Failed ingest returns status=failed with error."""
        with patch(
            "odyssey_rag.api.routes.ingest.ingest",
            AsyncMock(return_value=self._mock_ingest_result("failed")),
        ):
            resp = client.post(
                "/api/v1/ingest",
                json={"source_path": "/app/sources/bad.xml"},
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "failed"
        assert data["error"] is not None

    def test_ingest_missing_source_path_returns_422(self, client: TestClient):
        """Missing source_path fails validation."""
        resp = client.post("/api/v1/ingest", json={})
        assert resp.status_code == 422

    def test_ingest_batch(self, client: TestClient):
        """Batch ingest returns aggregated counts."""
        results = [
            self._mock_ingest_result("completed"),
            self._mock_ingest_result("skipped"),
        ]
        with patch(
            "odyssey_rag.api.routes.ingest.ingest",
            AsyncMock(side_effect=results),
        ):
            resp = client.post(
                "/api/v1/ingest/batch",
                json={
                    "sources": [
                        {"source_path": "/app/sources/a.md"},
                        {"source_path": "/app/sources/b.md"},
                    ]
                },
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2
        assert "completed" in data
        assert "skipped" in data
        assert "duration_ms" in data


# ---------------------------------------------------------------------------
# Sources
# ---------------------------------------------------------------------------


class TestSources:
    def _setup_doc_repo(self, mock_session, docs=None, total=None, doc=None):
        """Patch DocumentRepository methods on the mock session."""
        doc_repo = AsyncMock()
        doc_repo.list_current = AsyncMock(return_value=docs or [_make_doc()])
        doc_repo.count_current = AsyncMock(return_value=total if total is not None else 1)
        doc_repo.get_by_id = AsyncMock(return_value=doc or _make_doc())
        doc_repo.delete = AsyncMock(return_value=True)
        return doc_repo

    def _setup_chunk_repo(self, mock_session, chunks=None, count=None):
        """Patch ChunkRepository methods on the mock session."""
        chunk_repo = AsyncMock()
        chunk_repo.list_by_document = AsyncMock(return_value=chunks or [_make_chunk()])
        chunk_repo.count_by_document = AsyncMock(return_value=count if count is not None else 5)
        return chunk_repo

    def test_list_sources(self, client: TestClient):
        """GET /sources returns paginated list."""
        with (
            patch(
                "odyssey_rag.api.routes.sources.DocumentRepository"
            ) as MockDocRepo,
            patch("odyssey_rag.api.routes.sources.ChunkRepository"),
        ):
            mock_repo = AsyncMock()
            mock_repo.list_current = AsyncMock(return_value=[_make_doc()])
            mock_repo.count_current = AsyncMock(return_value=1)
            MockDocRepo.return_value = mock_repo

            resp = client.get("/api/v1/sources")

        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert len(data["items"]) == 1
        assert data["page"] == 1
        assert data["page_size"] == 50

    def test_list_sources_with_filter(self, client: TestClient):
        """source_type query param is forwarded to the repository."""
        with (
            patch(
                "odyssey_rag.api.routes.sources.DocumentRepository"
            ) as MockDocRepo,
            patch("odyssey_rag.api.routes.sources.ChunkRepository"),
        ):
            mock_repo = AsyncMock()
            mock_repo.list_current = AsyncMock(return_value=[])
            mock_repo.count_current = AsyncMock(return_value=0)
            MockDocRepo.return_value = mock_repo

            resp = client.get("/api/v1/sources?source_type=annex_b_spec")

        assert resp.status_code == 200
        mock_repo.list_current.assert_called_once()
        call_kwargs = mock_repo.list_current.call_args
        assert call_kwargs.kwargs.get("source_type") == "annex_b_spec"

    def test_get_source_detail(self, client: TestClient):
        """GET /sources/{id} returns document with chunk list."""
        with (
            patch(
                "odyssey_rag.api.routes.sources.DocumentRepository"
            ) as MockDocRepo,
            patch(
                "odyssey_rag.api.routes.sources.ChunkRepository"
            ) as MockChunkRepo,
        ):
            mock_doc_repo = AsyncMock()
            mock_doc_repo.get_by_id = AsyncMock(return_value=_make_doc())
            MockDocRepo.return_value = mock_doc_repo

            mock_chunk_repo = AsyncMock()
            mock_chunk_repo.list_by_document = AsyncMock(return_value=[_make_chunk()])
            MockChunkRepo.return_value = mock_chunk_repo

            resp = client.get(f"/api/v1/sources/{_DOC_ID}")

        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == str(_DOC_ID)
        assert len(data["chunks"]) == 1

    def test_get_source_not_found(self, client: TestClient):
        """GET /sources/{id} returns 404 when document doesn't exist."""
        with (
            patch(
                "odyssey_rag.api.routes.sources.DocumentRepository"
            ) as MockDocRepo,
            patch("odyssey_rag.api.routes.sources.ChunkRepository"),
        ):
            mock_doc_repo = AsyncMock()
            mock_doc_repo.get_by_id = AsyncMock(return_value=None)
            MockDocRepo.return_value = mock_doc_repo

            resp = client.get(f"/api/v1/sources/{uuid.uuid4()}")

        assert resp.status_code == 404

    def test_get_source_invalid_uuid(self, client: TestClient):
        """GET /sources/not-a-uuid returns 400."""
        resp = client.get("/api/v1/sources/not-a-uuid")
        assert resp.status_code == 400

    def test_delete_source(self, client: TestClient):
        """DELETE /sources/{id} returns deleted=True and chunk count."""
        with (
            patch(
                "odyssey_rag.api.routes.sources.DocumentRepository"
            ) as MockDocRepo,
            patch(
                "odyssey_rag.api.routes.sources.ChunkRepository"
            ) as MockChunkRepo,
        ):
            mock_doc_repo = AsyncMock()
            mock_doc_repo.get_by_id = AsyncMock(return_value=_make_doc())
            mock_doc_repo.delete = AsyncMock(return_value=True)
            MockDocRepo.return_value = mock_doc_repo

            mock_chunk_repo = AsyncMock()
            mock_chunk_repo.count_by_document = AsyncMock(return_value=5)
            MockChunkRepo.return_value = mock_chunk_repo

            resp = client.delete(f"/api/v1/sources/{_DOC_ID}")

        assert resp.status_code == 200
        data = resp.json()
        assert data["deleted"] is True
        assert data["chunks_deleted"] == 5

    def test_delete_source_not_found(self, client: TestClient):
        """DELETE /sources/{id} returns 404 when not found."""
        with (
            patch(
                "odyssey_rag.api.routes.sources.DocumentRepository"
            ) as MockDocRepo,
            patch("odyssey_rag.api.routes.sources.ChunkRepository"),
        ):
            mock_doc_repo = AsyncMock()
            mock_doc_repo.get_by_id = AsyncMock(return_value=None)
            MockDocRepo.return_value = mock_doc_repo

            resp = client.delete(f"/api/v1/sources/{uuid.uuid4()}")

        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Chunks
# ---------------------------------------------------------------------------


class TestChunks:
    def test_list_chunks(self, client: TestClient):
        """GET /chunks returns paginated chunk list."""
        with patch(
            "odyssey_rag.api.routes.chunks.ChunkRepository"
        ) as MockChunkRepo:
            mock_repo = AsyncMock()
            mock_repo.list_with_filters = AsyncMock(return_value=([_make_chunk()], 1))
            MockChunkRepo.return_value = mock_repo

            resp = client.get("/api/v1/chunks")

        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert len(data["items"]) == 1
        assert data["page"] == 1

    def test_list_chunks_with_filters(self, client: TestClient):
        """Query params are forwarded to list_with_filters."""
        with patch(
            "odyssey_rag.api.routes.chunks.ChunkRepository"
        ) as MockChunkRepo:
            mock_repo = AsyncMock()
            mock_repo.list_with_filters = AsyncMock(return_value=([], 0))
            MockChunkRepo.return_value = mock_repo

            resp = client.get(
                "/api/v1/chunks",
                params={
                    "document_id": str(_DOC_ID),
                    "message_type": "pacs.008",
                    "source_type": "annex_b_spec",
                    "section": "intro",
                },
            )

        assert resp.status_code == 200
        call_kwargs = mock_repo.list_with_filters.call_args
        assert call_kwargs.kwargs.get("message_type") == "pacs.008"
        assert call_kwargs.kwargs.get("source_type") == "annex_b_spec"
        assert call_kwargs.kwargs.get("section") == "intro"

    def test_list_chunks_invalid_document_id(self, client: TestClient):
        """Non-UUID document_id returns 400."""
        resp = client.get("/api/v1/chunks?document_id=not-a-uuid")
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# Feedback
# ---------------------------------------------------------------------------


class TestFeedback:
    def test_submit_feedback(self, client: TestClient):
        """POST /feedback creates a feedback record and returns 201."""
        feedback_id = uuid.uuid4()

        with patch(
            "odyssey_rag.api.routes.feedback.FeedbackRepository"
        ) as MockFeedbackRepo:
            mock_repo = AsyncMock()

            async def fake_insert(fb):
                fb.id = feedback_id
                return fb

            mock_repo.insert = fake_insert
            MockFeedbackRepo.return_value = mock_repo

            resp = client.post(
                "/api/v1/feedback",
                json={
                    "query": "pacs.008 fields",
                    "chunk_id": str(_CHUNK_ID),
                    "rating": 1,
                    "comment": "Very helpful",
                },
            )

        assert resp.status_code == 201
        data = resp.json()
        assert data["status"] == "accepted"
        assert "id" in data

    def test_submit_feedback_invalid_rating(self, client: TestClient):
        """Rating outside [-1, 1] fails validation."""
        resp = client.post(
            "/api/v1/feedback",
            json={"query": "q", "chunk_id": str(_CHUNK_ID), "rating": 2},
        )
        assert resp.status_code == 422

    def test_submit_feedback_invalid_chunk_id(self, client: TestClient):
        """Non-UUID chunk_id returns 400."""
        resp = client.post(
            "/api/v1/feedback",
            json={"query": "q", "chunk_id": "not-a-uuid", "rating": 1},
        )
        assert resp.status_code == 400

    def test_submit_feedback_missing_fields(self, client: TestClient):
        """Missing required fields return 422."""
        resp = client.post("/api/v1/feedback", json={"rating": 1})
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------


class TestAuth:
    def test_auth_required_without_key(self):
        """Endpoints return 401 when api_keys are configured and no key provided."""
        original = app.dependency_overrides.copy()
        app.dependency_overrides.clear()
        app.dependency_overrides[get_async_session] = lambda: AsyncMock()
        app.dependency_overrides[get_retrieval_engine] = lambda: MagicMock()

        with (
            patch("odyssey_rag.api.auth.get_settings") as mock_settings,
            patch("odyssey_rag.api.main.get_engine"),
            patch("odyssey_rag.api.main.close_engine", new=AsyncMock()),
        ):
            settings = MagicMock()
            settings.environment = "production"
            settings.api_keys = ["secret-key"]
            mock_settings.return_value = settings

            with TestClient(app) as c:
                resp = c.post("/api/v1/search", json={"query": "test"})

        app.dependency_overrides = original
        assert resp.status_code == 401

    def test_auth_dev_mode_no_keys(self):
        """Development mode with no keys configured bypasses auth."""
        original = app.dependency_overrides.copy()
        app.dependency_overrides.clear()
        app.dependency_overrides[get_retrieval_engine] = lambda: MagicMock(
            search=AsyncMock(return_value=_make_retrieval_response())
        )

        with (
            patch("odyssey_rag.api.auth.get_settings") as mock_settings,
            patch("odyssey_rag.api.main.get_engine"),
            patch("odyssey_rag.api.main.close_engine", new=AsyncMock()),
        ):
            settings = MagicMock()
            settings.environment = "development"
            settings.api_keys = []
            mock_settings.return_value = settings

            with TestClient(app) as c:
                resp = c.post("/api/v1/search", json={"query": "test"})

        app.dependency_overrides = original
        # Should not get a 401 — either 200 or another error (e.g. DB session)
        assert resp.status_code != 401


# ---------------------------------------------------------------------------
# Error format
# ---------------------------------------------------------------------------


class TestErrorFormat:
    def test_404_uses_consistent_format(self, client: TestClient):
        """Not-found errors include error_code field."""
        with (
            patch(
                "odyssey_rag.api.routes.sources.DocumentRepository"
            ) as MockDocRepo,
            patch("odyssey_rag.api.routes.sources.ChunkRepository"),
        ):
            mock_doc_repo = AsyncMock()
            mock_doc_repo.get_by_id = AsyncMock(return_value=None)
            MockDocRepo.return_value = mock_doc_repo

            resp = client.get(f"/api/v1/sources/{uuid.uuid4()}")

        assert resp.status_code == 404
        data = resp.json()
        assert "error_code" in data
        assert data["error_code"] == "NOT_FOUND"

    def test_422_uses_consistent_format(self, client: TestClient):
        """Validation errors include error_code=VALIDATION_ERROR."""
        resp = client.post("/api/v1/search", json={"query": ""})
        assert resp.status_code == 422
        data = resp.json()
        assert data["error_code"] == "VALIDATION_ERROR"
