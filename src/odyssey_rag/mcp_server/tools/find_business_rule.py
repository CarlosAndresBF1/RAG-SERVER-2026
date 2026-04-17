"""Handler for odyssey_rag.find_business_rule MCP tool.

Searches for Annex B validation rules, field constraints, and ISO code
definitions and their Odyssey validator implementation.
"""

from __future__ import annotations

from odyssey_rag.api.deps import get_retrieval_engine
from odyssey_rag.mcp_server.tools._output import to_mcp_output


async def find_business_rule_handler(
    message_type: str | None = None,
    rule_status: str | None = None,
    field_xpath: str | None = None,
    data_type: str | None = None,
    iso_code_type: str | None = None,
    keyword: str | None = None,
    top_k: int = 10,
) -> dict:
    """Return evidence for ISO 20022 validation rules and field constraints."""
    engine = get_retrieval_engine()

    parts: list[str] = []
    if message_type:
        parts.append(message_type)
    if rule_status:
        _labels = {"M": "Mandatory", "O": "Optional", "C": "Conditional", "R": "Required"}
        parts.append(_labels.get(rule_status, rule_status))
    if field_xpath:
        parts.append(field_xpath)
    if data_type:
        parts.append(data_type)
    if iso_code_type:
        parts.append(iso_code_type)
    if keyword:
        parts.append(keyword)
    if not parts:
        parts.append("validation rules business rules")
    query = " ".join(parts)

    tool_context: dict[str, str] = {"focus": "fields"}
    if message_type:
        tool_context["message_type"] = message_type
    if rule_status:
        tool_context["rule_status"] = rule_status

    response = await engine.search(
        query,
        tool_name="find_business_rule",
        tool_context=tool_context,
    )
    return to_mcp_output(response)
