"""MCP Server entrypoint for Odyssey RAG.

Supports dual transport: stdio (local dev) and HTTP/SSE (centralized team).
"""

from __future__ import annotations

import structlog

logger = structlog.get_logger(__name__)


def main() -> None:
    """Start the MCP server."""
    logger.info("mcp_server.starting", message="MCP server placeholder — not yet implemented")
    raise SystemExit(0)


if __name__ == "__main__":
    main()
