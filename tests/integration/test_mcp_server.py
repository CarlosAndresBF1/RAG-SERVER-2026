"""Integration tests for MCP server tool handlers.

These tests exercise the tool handler functions directly (bypassing FastMCP)
so the ``mcp`` package does not need to be installed locally.

All external I/O is mocked:
- ``get_retrieval_engine()`` → mock RetrievalEngine
- ``ingest()`` pipeline → mock IngestResult
"""

from __future__ import annotations

import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from odyssey_rag.retrieval.response_builder import Citation, Evidence, RetrievalResponse


# ── Helpers ───────────────────────────────────────────────────────────────────


def _make_response(
    query: str = "test query",
    evidence: list[Evidence] | None = None,
    gaps: list[str] | None = None,
    followups: list[str] | None = None,
) -> RetrievalResponse:
    """Build a minimal RetrievalResponse for testing."""
    return RetrievalResponse(
        query=query,
        evidence=evidence or [],
        gaps=gaps or [],
        followups=followups or [],
    )


def _make_evidence(
    text: str = "Some evidence text",
    relevance: float = 0.85,
    source_type: str = "annex_b_spec",
    message_type: str | None = "pacs.008",
    source_path: str = "docs/pacs008.md",
    section: str | None = "§ GrpHdr",
) -> Evidence:
    return Evidence(
        text=text,
        relevance=relevance,
        source_type=source_type,
        message_type=message_type,
        citations=[Citation(source_path=source_path, section=section, chunk_index=0)],
    )


@pytest.fixture
def mock_engine():
    """Mock RetrievalEngine whose search() returns a canned response."""
    engine = MagicMock()
    engine.search = AsyncMock()
    return engine


@pytest.fixture(autouse=True)
def patch_engine(mock_engine):
    """Patch get_retrieval_engine() for all tests in this module."""
    with patch("odyssey_rag.api.deps.get_retrieval_engine", return_value=mock_engine):
        with patch(
            "odyssey_rag.mcp_server.tools.find_message_type.get_retrieval_engine",
            return_value=mock_engine,
        ):
            with patch(
                "odyssey_rag.mcp_server.tools.find_business_rule.get_retrieval_engine",
                return_value=mock_engine,
            ):
                with patch(
                    "odyssey_rag.mcp_server.tools.find_module.get_retrieval_engine",
                    return_value=mock_engine,
                ):
                    with patch(
                        "odyssey_rag.mcp_server.tools.find_error.get_retrieval_engine",
                        return_value=mock_engine,
                    ):
                        with patch(
                            "odyssey_rag.mcp_server.tools.search.get_retrieval_engine",
                            return_value=mock_engine,
                        ):
                            yield mock_engine


# ── _output.to_mcp_output ─────────────────────────────────────────────────────


class TestToMcpOutput:
    def test_empty_response(self):
        from odyssey_rag.mcp_server.tools._output import to_mcp_output

        response = _make_response()
        result = to_mcp_output(response)

        assert result == {"evidence": [], "gaps": [], "followups": []}

    def test_with_evidence(self):
        from odyssey_rag.mcp_server.tools._output import to_mcp_output

        ev = _make_evidence(text="GrpHdr is mandatory", relevance=0.9)
        response = _make_response(evidence=[ev], gaps=["No XML example"], followups=["Try find_error"])
        result = to_mcp_output(response)

        assert len(result["evidence"]) == 1
        item = result["evidence"][0]
        assert item["score"] == 0.9
        assert item["snippet"] == "GrpHdr is mandatory"
        assert item["citations"][0]["source_type"] == "annex_b_spec"
        assert item["citations"][0]["source_id"] == "docs/pacs008.md"
        assert item["citations"][0]["locator"] == "§ GrpHdr"
        assert item["metadata"]["message_type"] == "pacs.008"
        assert result["gaps"] == ["No XML example"]
        assert result["followups"] == ["Try find_error"]

    def test_score_rounded_to_4dp(self):
        from odyssey_rag.mcp_server.tools._output import to_mcp_output

        ev = _make_evidence(relevance=0.123456789)
        response = _make_response(evidence=[ev])
        result = to_mcp_output(response)

        assert result["evidence"][0]["score"] == 0.1235

    def test_citation_empty_section(self):
        from odyssey_rag.mcp_server.tools._output import to_mcp_output

        ev = _make_evidence(section=None)
        response = _make_response(evidence=[ev])
        result = to_mcp_output(response)

        assert result["evidence"][0]["citations"][0]["locator"] == ""


# ── find_message_type handler ─────────────────────────────────────────────────


class TestFindMessageTypeHandler:
    @pytest.mark.asyncio
    async def test_basic_call(self, mock_engine):
        from odyssey_rag.mcp_server.tools.find_message_type import find_message_type_handler

        response = _make_response(evidence=[_make_evidence()])
        mock_engine.search.return_value = response

        result = await find_message_type_handler(message_type="pacs.008", focus="overview")

        mock_engine.search.assert_called_once()
        call_kwargs = mock_engine.search.call_args
        assert "pacs.008" in call_kwargs.args[0]
        assert call_kwargs.kwargs["tool_name"] == "find_message_type"
        assert call_kwargs.kwargs["tool_context"]["message_type"] == "pacs.008"
        assert call_kwargs.kwargs["tool_context"]["focus"] == "overview"
        assert "evidence" in result

    @pytest.mark.asyncio
    async def test_with_field_xpath(self, mock_engine):
        from odyssey_rag.mcp_server.tools.find_message_type import find_message_type_handler

        mock_engine.search.return_value = _make_response()

        await find_message_type_handler(
            message_type="pacs.008",
            focus="fields",
            field_xpath="GrpHdr/MsgId",
        )

        query_arg = mock_engine.search.call_args.args[0]
        assert "GrpHdr/MsgId" in query_arg
        context = mock_engine.search.call_args.kwargs["tool_context"]
        assert context["field_xpath"] == "GrpHdr/MsgId"

    @pytest.mark.asyncio
    async def test_output_has_standard_keys(self, mock_engine):
        from odyssey_rag.mcp_server.tools.find_message_type import find_message_type_handler

        mock_engine.search.return_value = _make_response(gaps=["gap1"], followups=["f1"])

        result = await find_message_type_handler(message_type="camt.056")

        assert set(result.keys()) == {"evidence", "gaps", "followups"}


# ── find_business_rule handler ────────────────────────────────────────────────


class TestFindBusinessRuleHandler:
    @pytest.mark.asyncio
    async def test_no_params_uses_fallback_query(self, mock_engine):
        from odyssey_rag.mcp_server.tools.find_business_rule import find_business_rule_handler

        mock_engine.search.return_value = _make_response()

        await find_business_rule_handler()

        query = mock_engine.search.call_args.args[0]
        assert "validation" in query.lower()

    @pytest.mark.asyncio
    async def test_rule_status_expanded(self, mock_engine):
        from odyssey_rag.mcp_server.tools.find_business_rule import find_business_rule_handler

        mock_engine.search.return_value = _make_response()

        await find_business_rule_handler(message_type="pacs.008", rule_status="M")

        query = mock_engine.search.call_args.args[0]
        assert "Mandatory" in query
        context = mock_engine.search.call_args.kwargs["tool_context"]
        assert context["rule_status"] == "M"
        assert context["message_type"] == "pacs.008"

    @pytest.mark.asyncio
    async def test_keyword_included(self, mock_engine):
        from odyssey_rag.mcp_server.tools.find_business_rule import find_business_rule_handler

        mock_engine.search.return_value = _make_response()

        await find_business_rule_handler(keyword="CLRG settlement", iso_code_type="LocalInstrumentCode")

        query = mock_engine.search.call_args.args[0]
        assert "CLRG" in query
        assert "LocalInstrumentCode" in query


# ── find_module handler ───────────────────────────────────────────────────────


class TestFindModuleHandler:
    @pytest.mark.asyncio
    async def test_module_map_in_output(self, mock_engine):
        from odyssey_rag.mcp_server.tools.find_module import find_module_handler

        ev = _make_evidence(source_path="Bimpay/Messages/Pacs008CreditTransfer.php")
        mock_engine.search.return_value = _make_response(evidence=[ev])

        result = await find_module_handler(module="Bimpay", focus="overview")

        assert "module_map" in result
        assert "key_files" in result["module_map"]
        key_files = result["module_map"]["key_files"]
        assert any("Pacs008" in kf["path"] for kf in key_files)

    @pytest.mark.asyncio
    async def test_query_includes_php_class(self, mock_engine):
        from odyssey_rag.mcp_server.tools.find_module import find_module_handler

        mock_engine.search.return_value = _make_response()

        await find_module_handler(
            module="Bimpay",
            focus="signing",
            php_class="XmlDSigSigner",
            php_symbol="wrapAndSign",
        )

        query = mock_engine.search.call_args.args[0]
        assert "XmlDSigSigner" in query
        assert "wrapAndSign" in query

    @pytest.mark.asyncio
    async def test_module_map_deduplicates_paths(self, mock_engine):
        from odyssey_rag.mcp_server.tools.find_module import find_module_handler

        same_path = "Bimpay/BaseMessage.php"
        ev1 = _make_evidence(source_path=same_path)
        ev2 = _make_evidence(source_path=same_path)
        mock_engine.search.return_value = _make_response(evidence=[ev1, ev2])

        result = await find_module_handler(module="Bimpay")

        paths = [kf["path"] for kf in result["module_map"]["key_files"]]
        assert paths.count(same_path) == 1


# ── find_error handler ────────────────────────────────────────────────────────


class TestFindErrorHandler:
    @pytest.mark.asyncio
    async def test_resolution_included(self, mock_engine):
        from odyssey_rag.mcp_server.tools.find_error import find_error_handler

        mock_engine.search.return_value = _make_response()

        result = await find_error_handler(iso_status="RJCT", reason_code="FF01")

        assert "resolution" in result
        assert "RJCT" in result["resolution"]["status_meaning"]
        assert "FF01" in result["resolution"]["reason_meaning"]

    @pytest.mark.asyncio
    async def test_known_status_meaning(self, mock_engine):
        from odyssey_rag.mcp_server.tools.find_error import find_error_handler

        mock_engine.search.return_value = _make_response()

        result = await find_error_handler(iso_status="ACSP")

        assert "settlement in process" in result["resolution"]["status_meaning"]

    @pytest.mark.asyncio
    async def test_unknown_code_graceful(self, mock_engine):
        from odyssey_rag.mcp_server.tools.find_error import find_error_handler

        mock_engine.search.return_value = _make_response()

        result = await find_error_handler(reason_code="ZZ99")

        assert "ZZ99" in result["resolution"]["reason_meaning"]
        assert "ISO 20022" in result["resolution"]["reason_meaning"]

    @pytest.mark.asyncio
    async def test_odyssey_touchpoints_from_evidence(self, mock_engine):
        from odyssey_rag.mcp_server.tools.find_error import find_error_handler

        ev = _make_evidence(source_path="Bimpay/XmlSchemaValidator.php")
        mock_engine.search.return_value = _make_response(evidence=[ev])

        result = await find_error_handler(iso_status="RJCT", reason_code="FF01")

        touchpoints = result["resolution"].get("odyssey_touchpoints", [])
        assert any("XmlSchemaValidator" in tp["path"] for tp in touchpoints)

    @pytest.mark.asyncio
    async def test_no_args_fallback_query(self, mock_engine):
        from odyssey_rag.mcp_server.tools.find_error import find_error_handler

        mock_engine.search.return_value = _make_response()

        await find_error_handler()

        query = mock_engine.search.call_args.args[0]
        assert len(query) > 0


# ── search handler ────────────────────────────────────────────────────────────


class TestSearchHandler:
    @pytest.mark.asyncio
    async def test_basic_search(self, mock_engine):
        from odyssey_rag.mcp_server.tools.search import search_handler

        ev = _make_evidence(text="Polling service uses mTLS")
        mock_engine.search.return_value = _make_response(evidence=[ev])

        result = await search_handler(query="How does the poller work?")

        mock_engine.search.assert_called_once()
        assert result["evidence"][0]["snippet"] == "Polling service uses mTLS"

    @pytest.mark.asyncio
    async def test_with_message_type(self, mock_engine):
        from odyssey_rag.mcp_server.tools.search import search_handler

        mock_engine.search.return_value = _make_response()

        await search_handler(query="settlement flow", message_type="pacs.008")

        context = mock_engine.search.call_args.kwargs["tool_context"]
        assert context["message_type"] == "pacs.008"

    @pytest.mark.asyncio
    async def test_no_message_type_none_context(self, mock_engine):
        from odyssey_rag.mcp_server.tools.search import search_handler

        mock_engine.search.return_value = _make_response()

        await search_handler(query="Montran envelope")

        call_kwargs = mock_engine.search.call_args.kwargs
        # When message_type is None, tool_context is None (empty dict is falsy)
        assert call_kwargs.get("tool_context") is None


# ── ingest handler ────────────────────────────────────────────────────────────


class TestIngestHandler:
    @pytest.mark.asyncio
    async def test_successful_ingest(self):
        from odyssey_rag.ingestion.pipeline import IngestResult
        from odyssey_rag.mcp_server.tools.ingest import ingest_handler

        mock_result = IngestResult(
            status="completed",
            source_path="new-doc.md",
            source_type="tech_doc",
            chunks_created=12,
        )

        with patch(
            "odyssey_rag.mcp_server.tools.ingest.ingest",
            new=AsyncMock(return_value=mock_result),
        ):
            result = await ingest_handler(source="new-doc.md")

        assert result["status"] == "completed"
        assert result["source"] == "new-doc.md"
        assert result["chunks_created"] == 12
        assert result["source_type_detected"] == "tech_doc"
        assert result["errors"] == []

    @pytest.mark.asyncio
    async def test_failed_ingest_surfaces_error(self):
        from odyssey_rag.ingestion.pipeline import IngestResult
        from odyssey_rag.mcp_server.tools.ingest import ingest_handler

        mock_result = IngestResult(
            status="failed",
            source_path="bad-file.xyz",
            source_type="",
            chunks_created=0,
            error="Unsupported file type",
        )

        with patch(
            "odyssey_rag.mcp_server.tools.ingest.ingest",
            new=AsyncMock(return_value=mock_result),
        ):
            result = await ingest_handler(source="bad-file.xyz")

        assert result["status"] == "failed"
        assert "Unsupported file type" in result["errors"]

    @pytest.mark.asyncio
    async def test_source_type_override(self):
        from odyssey_rag.ingestion.pipeline import IngestResult
        from odyssey_rag.mcp_server.tools.ingest import ingest_handler

        mock_result = IngestResult(
            status="completed",
            source_path="spec.md",
            source_type="annex_b_spec",
            chunks_created=5,
        )

        with patch(
            "odyssey_rag.mcp_server.tools.ingest.ingest",
            new=AsyncMock(return_value=mock_result),
        ) as mock_ingest:
            await ingest_handler(
                source="spec.md",
                source_type="annex_b_spec",
                replace_existing=True,
            )

        mock_ingest.assert_called_once_with(
            source_path="spec.md",
            overrides={"source_type": "annex_b_spec"},
            replace_existing=True,
        )

    @pytest.mark.asyncio
    async def test_no_source_type_passes_none_overrides(self):
        from odyssey_rag.ingestion.pipeline import IngestResult
        from odyssey_rag.mcp_server.tools.ingest import ingest_handler

        mock_result = IngestResult(
            status="completed",
            source_path="doc.md",
            source_type="generic_text",
            chunks_created=3,
        )

        with patch(
            "odyssey_rag.mcp_server.tools.ingest.ingest",
            new=AsyncMock(return_value=mock_result),
        ) as mock_ingest:
            await ingest_handler(source="doc.md")

        mock_ingest.assert_called_once_with(
            source_path="doc.md",
            overrides=None,
            replace_existing=False,
        )


# ── main.py argument parsing ──────────────────────────────────────────────────


class TestMainArgParsing:
    def test_default_transport_is_stdio(self):
        from odyssey_rag.mcp_server.main import _parse_args

        args = _parse_args([])
        assert args.transport == "stdio"

    def test_http_transport(self):
        from odyssey_rag.mcp_server.main import _parse_args

        args = _parse_args(["--transport", "http", "--port", "9000"])
        assert args.transport == "http"
        assert args.port == 9000

    def test_main_exits_without_mcp_package(self):
        """main() should exit gracefully when mcp is not installed."""
        from odyssey_rag.mcp_server.main import main

        with patch.dict(sys.modules, {"mcp": None, "mcp.server": None, "mcp.server.fastmcp": None}):
            with patch(
                "odyssey_rag.mcp_server.server.create_server",
                side_effect=ImportError("No module named 'mcp'"),
            ):
                with pytest.raises(SystemExit) as exc_info:
                    main(["--transport", "stdio"])

                assert exc_info.value.code == 1
