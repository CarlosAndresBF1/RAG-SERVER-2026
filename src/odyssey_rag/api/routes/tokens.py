"""MCP Token management — CRUD + audit log.

POST   /api/v1/tokens              Create token (receives hash from UI)
GET    /api/v1/tokens              List active tokens (no hash exposed)
DELETE /api/v1/tokens/{id}         Revoke token
GET    /api/v1/tokens/{id}/audit   Audit log for a token
"""

from __future__ import annotations

import uuid as uuid_mod
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel
from sqlalchemy import desc, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from odyssey_rag.api.deps import get_async_session
from odyssey_rag.db.models import AdminUser, McpToken, McpTokenAudit

router = APIRouter(prefix="/tokens", tags=["tokens"])


# ── Request / Response schemas ────────────────────────────────────────


class CreateTokenRequest(BaseModel):
    name: str
    token_hash: str
    token_prefix: str
    issued_by: Optional[str] = None  # admin_user UUID (resolved server-side if absent)
    scopes: list[str] = ["read"]
    expires_at: Optional[str] = None  # ISO 8601 or None
    rate_limit_rpm: int = 60


class TokenResponse(BaseModel):
    id: str
    name: str
    token_prefix: str
    scopes: list[str]
    is_active: bool
    expires_at: Optional[str]
    last_used_at: Optional[str]
    usage_count: int
    rate_limit_rpm: int
    created_at: str
    revoked_at: Optional[str]


class AuditEntry(BaseModel):
    id: str
    action: str
    ip_address: Optional[str]
    user_agent: Optional[str]
    tool_name: Optional[str]
    created_at: str


# ── Helpers ───────────────────────────────────────────────────────────


def _token_to_response(t: McpToken) -> TokenResponse:
    return TokenResponse(
        id=str(t.id),
        name=t.name,
        token_prefix=t.token_prefix,
        scopes=t.scopes,
        is_active=t.is_active,
        expires_at=t.expires_at.isoformat() if t.expires_at else None,
        last_used_at=t.last_used_at.isoformat() if t.last_used_at else None,
        usage_count=t.usage_count,
        rate_limit_rpm=t.rate_limit_rpm,
        created_at=t.created_at.isoformat(),
        revoked_at=t.revoked_at.isoformat() if t.revoked_at else None,
    )


# ── Endpoints ─────────────────────────────────────────────────────────


@router.post("", response_model=TokenResponse, status_code=201)
async def create_token(
    body: CreateTokenRequest,
    db: AsyncSession = Depends(get_async_session),
) -> TokenResponse:
    """Create a new MCP token record (the UI sends the hash, not the raw token)."""
    expires = (
        datetime.fromisoformat(body.expires_at) if body.expires_at else None
    )

    # Resolve issued_by: use provided UUID or fall back to first active admin
    if body.issued_by:
        issuer_id = uuid_mod.UUID(body.issued_by)
    else:
        result = await db.execute(
            select(AdminUser.id).where(AdminUser.is_active == True).limit(1)
        )
        admin_id = result.scalar_one_or_none()
        if not admin_id:
            raise HTTPException(status_code=400, detail="No active admin user found")
        issuer_id = admin_id

    token = McpToken(
        name=body.name,
        token_hash=body.token_hash,
        token_prefix=body.token_prefix,
        issued_by=issuer_id,
        scopes=body.scopes,
        expires_at=expires,
        rate_limit_rpm=body.rate_limit_rpm,
    )
    db.add(token)
    await db.flush()

    # Audit: created
    db.add(McpTokenAudit(token_id=token.id, action="created"))
    await db.flush()

    # Refresh to load server-generated defaults (created_at, etc.)
    await db.refresh(token)

    return _token_to_response(token)


@router.get("", response_model=list[TokenResponse])
async def list_tokens(
    db: AsyncSession = Depends(get_async_session),
) -> list[TokenResponse]:
    """List all tokens (active and revoked). Hash is never returned."""
    stmt = select(McpToken).order_by(desc(McpToken.created_at))
    result = await db.execute(stmt)
    tokens = result.scalars().all()
    return [_token_to_response(t) for t in tokens]


@router.delete("/{token_id}", status_code=204)
async def revoke_token(
    token_id: str,
    db: AsyncSession = Depends(get_async_session),
):
    """Revoke an MCP token by setting is_active=False."""
    tid = uuid_mod.UUID(token_id)
    stmt = select(McpToken).where(McpToken.id == tid)
    result = await db.execute(stmt)
    token = result.scalar_one_or_none()

    if not token:
        raise HTTPException(status_code=404, detail="Token not found")

    token.is_active = False
    token.revoked_at = datetime.now(timezone.utc)

    db.add(McpTokenAudit(token_id=token.id, action="revoked"))
    await db.flush()
    return Response(status_code=204)


@router.get("/{token_id}/audit", response_model=list[AuditEntry])
async def get_token_audit(
    token_id: str,
    limit: int = 100,
    db: AsyncSession = Depends(get_async_session),
) -> list[AuditEntry]:
    """Get audit log entries for a specific token."""
    tid = uuid_mod.UUID(token_id)
    stmt = (
        select(McpTokenAudit)
        .where(McpTokenAudit.token_id == tid)
        .order_by(desc(McpTokenAudit.created_at))
        .limit(limit)
    )
    result = await db.execute(stmt)
    entries = result.scalars().all()

    return [
        AuditEntry(
            id=str(e.id),
            action=e.action,
            ip_address=e.ip_address,
            user_agent=e.user_agent,
            tool_name=e.tool_name,
            created_at=e.created_at.isoformat(),
        )
        for e in entries
    ]
