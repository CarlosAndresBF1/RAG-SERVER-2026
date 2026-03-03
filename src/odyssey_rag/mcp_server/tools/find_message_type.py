"""Handler for oddysey_rag.find_message_type MCP tool.

Retrieves evidence for an ISO 20022 message type from Annex B spec,
PHP code, and XML examples.
"""

from __future__ import annotations

from odyssey_rag.api.deps import get_retrieval_engine
from odyssey_rag.mcp_server.tools._output import to_mcp_output


async def find_message_type_handler(
    message_type: str,
    focus: str = "overview",
    field_xpath: str | None = None,
    top_k: int = 8,
) -> dict:
    """Return evidence for an ISO 20022 message type and its Odyssey implementation."""
    engine = get_retrieval_engine()

    parts = [message_type, focus]
    if field_xpath:
        parts.append(field_xpath)
    query = " ".join(parts)

    tool_context: dict[str, str] = {
        "message_type": message_type,
        "focus": focus,
    }
    if field_xpath:
        tool_context["field_xpath"] = field_xpath

    response = await engine.search(
        query,
        tool_name="find_message_type",
        tool_context=tool_context,
    )
    return to_mcp_output(response)
