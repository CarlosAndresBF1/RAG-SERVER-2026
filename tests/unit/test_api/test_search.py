"""Tests for POST /api/v1/search endpoint."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from odyssey_rag.api.deps import get_retrieval_engine
from odyssey_rag.retrieval.response_builder import (
    Citation,
    Evidence,
    RetrievalResponse,
)

# ── Helpers ───────────────────────────────────────────────────────────────────


def _make_retrieval_response(**overrides) -> RetrievalResponse:
    defaults = {
        "query": "test query",
        "evidence": [
            Evidence(
                text="Relevant text about pacs.008",
                relevance=0.95,
                citations=[
                    Citation(
                        source_path="/data/spec.md",
                        section="Overview",
                        chunk_index=0,
                    )
                ],
                message_type="pacs.008",
                source_type="annex_b_spec",
            )
        ],
        "gaps": ["No envelope documentation found"],
        "followups": ["Try searching for pacs.008 fields"],
    }
    defaults.update(overrides)
    return RetrievalResponse(**defaults)


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


class TestSearchEndpoint:
    """Tests for POST /api/v1/search."""

    async def test_search_success(self, client: AsyncClient, app) -> None:
        mock_engine = MagicMock()
        mock_engine.search = AsyncMock(
            return_value=_make_retrieval_response(),
        )
        app.dependency_overrides[get_retrieval_engine] = lambda: mock_engine

        resp = await client.post(
            "/api/v1/search", json={"query": "What is pacs.008?"},
        )

        app.dependency_overrides.clear()
        assert resp.status_code == 200
        data = resp.json()
        assert data["query"] == "test query"
        assert len(data["evidence"]) == 1
        assert data["evidence"][0]["relevance"] == 0.95
        assert len(data["evidence"][0]["citations"]) == 1
        assert "metadata" in data
        assert "search_time_ms" in data["metadata"]

    async def test_search_with_filters(self, client: AsyncClient, app) -> None:
        mock_engine = MagicMock()
        mock_engine.search = AsyncMock(
            return_value=_make_retrieval_response(),
        )
        app.dependency_overrides[get_retrieval_engine] = lambda: mock_engine

        resp = await client.post(
            "/api/v1/search",
            json={
                "query": "mandatory fields",
                "message_type": "pacs.008",
                "source_type": "annex_b_spec",
                "focus": "fields",
            },
        )

        app.dependency_overrides.clear()
        assert resp.status_code == 200
        call_kwargs = mock_engine.search.call_args.kwargs
        assert call_kwargs["tool_context"]["message_type"] == "pacs.008"
        assert call_kwargs["tool_context"]["source_type"] == "annex_b_spec"
        assert call_kwargs["tool_context"]["focus"] == "fields"

    async def test_search_empty_query_rejected(
        self, client: AsyncClient, app,
    ) -> None:
        mock_engine = MagicMock()
        app.dependency_overrides[get_retrieval_engine] = lambda: mock_engine

        resp = await client.post("/api/v1/search", json={"query": ""})

        app.dependency_overrides.clear()
        assert resp.status_code == 422

    async def test_search_invalid_message_type_rejected(
        self, client: AsyncClient, app,
    ) -> None:
        mock_engine = MagicMock()
        app.dependency_overrides[get_retrieval_engine] = lambda: mock_engine

        resp = await client.post(
            "/api/v1/search",
            json={"query": "test", "message_type": "invalid"},
        )

        app.dependency_overrides.clear()
        assert resp.status_code == 422

    async def test_search_invalid_focus_rejected(
        self, client: AsyncClient, app,
    ) -> None:
        mock_engine = MagicMock()
        app.dependency_overrides[get_retrieval_engine] = lambda: mock_engine

        resp = await client.post(
            "/api/v1/search",
            json={"query": "test", "focus": "bad_focus"},
        )

        app.dependency_overrides.clear()
        assert resp.status_code == 422

    async def test_search_no_results(self, client: AsyncClient, app) -> None:
        mock_engine = MagicMock()
        mock_engine.search = AsyncMock(
            return_value=_make_retrieval_response(
                evidence=[], gaps=["Nothing found"], followups=[],
            ),
        )
        app.dependency_overrides[get_retrieval_engine] = lambda: mock_engine

        resp = await client.post(
            "/api/v1/search", json={"query": "nonexistent topic"},
        )

        app.dependency_overrides.clear()
        assert resp.status_code == 200
        data = resp.json()
        assert data["evidence"] == []
        assert len(data["gaps"]) == 1
