"""MCP Server entrypoint for Odyssey RAG.

Supports dual transport:
  - stdio   — local dev, VS Code Copilot/Claude Code direct process
  - http    — centralized team server, HTTP/SSE transport

Usage:
    python -m odyssey_rag.mcp_server                   # defaults to stdio
    python -m odyssey_rag.mcp_server --transport stdio
    python -m odyssey_rag.mcp_server --transport http --host 0.0.0.0 --port 8081
"""

from __future__ import annotations

import argparse
import os
import sys

import structlog

logger = structlog.get_logger(__name__)


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse CLI arguments, with environment variable fallbacks for Docker."""
    parser = argparse.ArgumentParser(
        description="Odyssey RAG MCP Server",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--transport",
        choices=["stdio", "http"],
        default=os.environ.get("MCP_TRANSPORT", "stdio"),
        help="Transport layer to use. Env: MCP_TRANSPORT.",
    )
    parser.add_argument(
        "--host",
        default=os.environ.get("MCP_HOST", "0.0.0.0"),
        help="Host to bind to (http transport only). Env: MCP_HOST.",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.environ.get("MCP_PORT", "8081")),
        help="Port to listen on (http transport only). Env: MCP_PORT.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    """Start the MCP server with the selected transport."""
    args = _parse_args(argv)
    logger.info("mcp_server.starting", transport=args.transport)

    try:
        from odyssey_rag.mcp_server.server import create_server

        mcp = create_server()
    except ImportError as exc:
        logger.error(
            "mcp_server.import_failed",
            error=str(exc),
            hint="Install the 'mcp' package: pip install 'mcp>=1.0.0' (requires Python 3.10+)",
        )
        sys.exit(1)

    if args.transport == "stdio":
        logger.info("mcp_server.stdio_start")
        mcp.run(transport="stdio")
    else:
        import uvicorn
        from starlette.responses import JSONResponse
        from starlette.routing import Route

        from odyssey_rag.mcp_server.auth_middleware import McpTokenAuthMiddleware

        logger.info("mcp_server.http_start", host=args.host, port=args.port)

        # Use streamable HTTP transport (MCP 2025-03-26 spec)
        # Endpoint: POST /mcp
        app = mcp.streamable_http_app()

        # ── Health endpoint (public, no auth) ─────────────────────────────
        async def _health_endpoint(request):
            return JSONResponse({"status": "ok"})

        app.routes.insert(0, Route("/health", _health_endpoint, methods=["GET"]))

        app.add_middleware(McpTokenAuthMiddleware)
        uvicorn.run(app, host=args.host, port=args.port, log_level="info")


if __name__ == "__main__":
    main()
