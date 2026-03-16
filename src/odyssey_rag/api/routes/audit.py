"""Audit log endpoint — GET /api/v1/audit.

Returns MCP token audit log entries.
"""

from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Depends, Query
from sqlalchemy import desc, select, func
from sqlalchemy.ext.asyncio import AsyncSession

from odyssey_rag.api.auth import verify_api_key
from odyssey_rag.api.deps import get_async_session
from odyssey_rag.db.models import McpTokenAudit

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("")
async def list_audit_entries(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    action: str | None = None,
    session: AsyncSession = Depends(get_async_session),
    _: str = Depends(verify_api_key),
) -> Dict[str, Any]:
    base = select(McpTokenAudit)
    count_base = select(func.count()).select_from(McpTokenAudit)

    if action:
        base = base.where(McpTokenAudit.action == action)
        count_base = count_base.where(McpTokenAudit.action == action)

    total = await session.scalar(count_base) or 0
    offset = (page - 1) * page_size
    stmt = base.order_by(desc(McpTokenAudit.created_at)).limit(page_size).offset(offset)
    result = await session.execute(stmt)
    entries = result.scalars().all()

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "entries": [
            {
                "id": str(e.id),
                "token_id": str(e.token_id),
                "action": e.action,
                "ip_address": str(e.ip_address) if e.ip_address else None,
                "user_agent": e.user_agent,
                "tool_name": e.tool_name,
                "created_at": e.created_at.isoformat() if e.created_at else None,
            }
            for e in entries
        ],
    }
