"""Handler for odyssey_rag.search MCP tool.

Free-text semantic search across all indexed Odyssey/Bimpay/IPS
documentation and code. Fallback when domain-specific tools don't apply.
"""

from __future__ import annotations

from odyssey_rag.api.deps import get_retrieval_engine
from odyssey_rag.mcp_server.tools._output import to_mcp_output


async def search_handler(
    query: str,
    message_type: str | None = None,
    integration: str | None = None,
    top_k: int = 8,
) -> dict:
    """Return evidence for a free-text semantic query."""
    engine = get_retrieval_engine()

    tool_context: dict[str, str] = {}
    if message_type:
        tool_context["message_type"] = message_type
    if integration:
        tool_context["integration"] = integration

    response = await engine.search(
        query,
        tool_name="search",
        tool_context=tool_context or None,
    )
    return to_mcp_output(response)
