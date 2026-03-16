"""MCP token authentication middleware.

Validates Bearer tokens in the Authorization header against the mcp_token table.
Tokens are hashed with SHA-256 and compared to stored hashes.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone

import structlog
from sqlalchemy import select, update
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

logger = structlog.get_logger(__name__)


class McpTokenAuthMiddleware(BaseHTTPMiddleware):
    """Starlette middleware that validates MCP Bearer tokens."""

    async def dispatch(self, request: Request, call_next):
        # Allow health-check / CORS preflight through
        if request.method == "OPTIONS":
            return await call_next(request)

        # In development mode without MCP_AUTH_REQUIRED, skip auth
        import os
        if os.environ.get("MCP_AUTH_REQUIRED", "false").lower() != "true":
            return await call_next(request)

        auth_header = request.headers.get("authorization", "")
        if not auth_header.startswith("Bearer "):
            return JSONResponse(
                status_code=401,
                content={"error": "Missing or invalid Authorization header"},
            )

        raw_token = auth_header[7:]  # Strip "Bearer "
        token_hash = hashlib.sha256(raw_token.encode()).hexdigest()

        # Validate against DB
        from odyssey_rag.db.session import get_session_factory
        from odyssey_rag.db.models import McpToken, McpTokenAudit

        factory = get_session_factory()
        async with factory() as session:
            stmt = select(McpToken).where(
                McpToken.token_hash == token_hash,
                McpToken.is_active == True,
            )
            result = await session.execute(stmt)
            token = result.scalar_one_or_none()

            if not token:
                logger.warning("mcp_auth.invalid_token", prefix=raw_token[:8] if len(raw_token) >= 8 else "***")
                return JSONResponse(
                    status_code=401,
                    content={"error": "Invalid or revoked token"},
                )

            # Check expiry
            if token.expires_at and token.expires_at < datetime.now(timezone.utc):
                logger.warning("mcp_auth.expired_token", prefix=token.token_prefix)
                return JSONResponse(
                    status_code=401,
                    content={"error": "Token has expired"},
                )

            # Update usage stats
            token.usage_count += 1
            token.last_used_at = datetime.now(timezone.utc)

            # Audit log
            session.add(McpTokenAudit(
                token_id=token.id,
                action="used",
                ip_address=request.client.host if request.client else None,
                user_agent=request.headers.get("user-agent", "")[:500],
            ))
            await session.commit()

            # Store scopes on request state for downstream use
            request.state.token_scopes = token.scopes
            request.state.token_id = str(token.id)

        return await call_next(request)
