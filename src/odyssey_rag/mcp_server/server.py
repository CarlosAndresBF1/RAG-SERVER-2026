"""FastMCP server instance and tool registration.

This module creates the shared FastMCP app instance and registers all
6 Odyssey RAG tools.  Import this module to get the configured server;
call ``mcp.run()`` to start it.

Note: ``mcp`` is imported lazily so that the tools module can be imported
in tests without needing the MCP library installed locally.  The library is
required at runtime (Docker image) but not at test time.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover
    pass


def create_server():
    """Create and return a configured FastMCP server with all tools registered.

    Imported lazily so that the mcp package is only required at runtime.
    """
    from mcp.server.fastmcp import FastMCP

    from odyssey_rag.mcp_server.tools.find_business_rule import find_business_rule_handler
    from odyssey_rag.mcp_server.tools.find_error import find_error_handler
    from odyssey_rag.mcp_server.tools.find_message_type import find_message_type_handler
    from odyssey_rag.mcp_server.tools.find_module import find_module_handler
    from odyssey_rag.mcp_server.tools.ingest import ingest_handler
    from odyssey_rag.mcp_server.tools.search import search_handler

    mcp = FastMCP(
        "oddysey-rag",
        description="RAG system for ISO 20022 / Odyssey / Bimpay IPS domain knowledge",
    )

    # ── Register tools using the handler functions ────────────────────────────

    @mcp.tool(
        name="oddysey_rag.find_message_type",
        description=(
            "Retrieve evidence (Annex B spec, PHP code, XML examples) for an ISO 20022 "
            "message type and its Odyssey implementation."
        ),
    )
    async def find_message_type(
        message_type: str,
        focus: str = "overview",
        field_xpath: str = "",
        top_k: int = 8,
    ) -> dict:
        return await find_message_type_handler(
            message_type=message_type,
            focus=focus,
            field_xpath=field_xpath or None,
            top_k=top_k,
        )

    @mcp.tool(
        name="oddysey_rag.find_business_rule",
        description=(
            "Search for Annex B validation rules (M/O/C/R), field constraints, "
            "ISO code definitions, and their Odyssey validator implementation."
        ),
    )
    async def find_business_rule(
        message_type: str = "",
        rule_status: str = "",
        field_xpath: str = "",
        data_type: str = "",
        iso_code_type: str = "",
        keyword: str = "",
        top_k: int = 10,
    ) -> dict:
        return await find_business_rule_handler(
            message_type=message_type or None,
            rule_status=rule_status or None,
            field_xpath=field_xpath or None,
            data_type=data_type or None,
            iso_code_type=iso_code_type or None,
            keyword=keyword or None,
            top_k=top_k,
        )

    @mcp.tool(
        name="oddysey_rag.find_module",
        description=(
            "Map Odyssey implementation: file paths, PHP classes, key methods, "
            "tests, and architecture for a given module or integration area."
        ),
    )
    async def find_module(
        module: str,
        focus: str = "overview",
        php_class: str = "",
        php_symbol: str = "",
        top_k: int = 15,
    ) -> dict:
        return await find_module_handler(
            module=module,
            focus=focus,
            php_class=php_class or None,
            php_symbol=php_symbol or None,
            top_k=top_k,
        )

    @mcp.tool(
        name="oddysey_rag.find_error",
        description=(
            "Troubleshoot ISO 20022 errors: transaction status codes (RJCT/ACSP/PDNG), "
            "reason codes (AC03/FF01/AM04), and Odyssey error handling implementation."
        ),
    )
    async def find_error(
        iso_status: str = "",
        reason_code: str = "",
        code_type: str = "",
        message_type_hint: str = "",
        error_fragment: str = "",
        top_k: int = 10,
    ) -> dict:
        return await find_error_handler(
            iso_status=iso_status or None,
            reason_code=reason_code or None,
            code_type=code_type or None,
            message_type_hint=message_type_hint or None,
            error_fragment=error_fragment or None,
            top_k=top_k,
        )

    @mcp.tool(
        name="oddysey_rag.search",
        description=(
            "Free-text semantic search across all indexed Odyssey/Bimpay/IPS "
            "documentation and code. Use when domain-specific tools don't cover the query."
        ),
    )
    async def search(
        query: str,
        message_type: str = "",
        top_k: int = 8,
    ) -> dict:
        return await search_handler(
            query=query,
            message_type=message_type or None,
            top_k=top_k,
        )

    @mcp.tool(
        name="oddysey_rag.ingest",
        description=(
            "Ingest new documents into the Odyssey RAG knowledge base. "
            "Supports Markdown, PHP code, XML examples, PDFs, and Postman collections."
        ),
    )
    async def ingest(
        source: str,
        source_type: str = "",
        replace_existing: bool = False,
    ) -> dict:
        return await ingest_handler(
            source=source,
            source_type=source_type or None,
            replace_existing=replace_existing,
        )

    return mcp
