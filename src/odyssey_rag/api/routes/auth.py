"""Admin authentication endpoint — POST /api/v1/auth/verify.

Used by NextAuth.js credentials provider to verify admin login.
"""

from __future__ import annotations

import bcrypt
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timezone

from odyssey_rag.api.deps import get_async_session
from odyssey_rag.db.models import AdminUser

router = APIRouter(prefix="/auth", tags=["auth"])


class AuthRequest(BaseModel):
    email: str
    password: str


class AuthResponse(BaseModel):
    id: str
    email: str
    name: str
    role: str


@router.post("/verify", response_model=AuthResponse)
async def verify_credentials(
    body: AuthRequest,
    db: AsyncSession = Depends(get_async_session),
) -> AuthResponse:
    """Verify admin credentials. Returns user info or 401."""
    stmt = select(AdminUser).where(
        AdminUser.email == body.email,
        AdminUser.is_active == True,
    )
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    if not bcrypt.checkpw(
        body.password.encode("utf-8"),
        user.password_hash.encode("utf-8"),
    ):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    # Update last_login_at
    await db.execute(
        update(AdminUser)
        .where(AdminUser.id == user.id)
        .values(last_login_at=datetime.now(timezone.utc))
    )

    return AuthResponse(
        id=str(user.id),
        email=user.email,
        name=user.display_name,
        role=user.role,
    )
