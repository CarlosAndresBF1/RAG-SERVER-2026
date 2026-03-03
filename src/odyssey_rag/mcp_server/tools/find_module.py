"""Handler for oddysey_rag.find_module MCP tool.

Maps Odyssey implementation: file paths, PHP classes, key methods,
and architecture for a given module or integration area.

Returns standard evidence + extended ``module_map`` derived from citations.
"""

from __future__ import annotations

from odyssey_rag.api.deps import get_retrieval_engine
from odyssey_rag.mcp_server.tools._output import to_mcp_output


def _build_module_map(response) -> dict:
    """Derive a lightweight module map from evidence citations."""
    seen: dict[str, dict] = {}
    for item in response.evidence:
        for citation in item.citations:
            path = citation.source_path
            if path and path not in seen:
                seen[path] = {
                    "path": path,
                    "source_type": item.source_type,
                    "section": citation.section or "",
                }

    key_files = [
        {"path": v["path"], "source_type": v["source_type"], "section": v["section"]}
        for v in seen.values()
    ]
    return {"key_files": key_files}


async def find_module_handler(
    module: str,
    focus: str = "overview",
    php_class: str | None = None,
    php_symbol: str | None = None,
    top_k: int = 15,
) -> dict:
    """Return evidence and module_map for an Odyssey module or integration area."""
    engine = get_retrieval_engine()

    parts = [module, focus]
    if php_class:
        parts.append(php_class)
    if php_symbol:
        parts.append(php_symbol)
    query = " ".join(parts)

    tool_context: dict[str, str] = {"focus": focus}
    if php_class:
        tool_context["php_class"] = php_class
    if php_symbol:
        tool_context["php_symbol"] = php_symbol

    response = await engine.search(
        query,
        tool_name="find_module",
        tool_context=tool_context,
    )

    output = to_mcp_output(response)
    output["module_map"] = _build_module_map(response)
    return output
