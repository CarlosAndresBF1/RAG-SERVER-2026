"""Admin user management endpoints.

Routes:
    GET    /api/v1/admin/users
    POST   /api/v1/admin/users
    DELETE /api/v1/admin/users/{user_id}
"""

from __future__ import annotations

import uuid

import bcrypt
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from odyssey_rag.api.auth import verify_api_key
from odyssey_rag.api.deps import get_async_session
from odyssey_rag.db.models import AdminUser

router = APIRouter(prefix="/admin", tags=["admin"])


class CreateUserRequest(BaseModel):
    email: str
    password: str
    display_name: str
    role: str = "admin"


@router.get("/users")
async def list_users(
    session: AsyncSession = Depends(get_async_session),
    _: str = Depends(verify_api_key),
):
    stmt = select(AdminUser).order_by(AdminUser.created_at.desc())
    result = await session.execute(stmt)
    users = result.scalars().all()
    return {
        "users": [
            {
                "id": str(u.id),
                "email": u.email,
                "display_name": u.display_name,
                "role": u.role,
                "is_active": u.is_active,
                "last_login_at": u.last_login_at.isoformat() if u.last_login_at else None,
                "created_at": u.created_at.isoformat() if u.created_at else None,
            }
            for u in users
        ]
    }


@router.post("/users", status_code=201)
async def create_user(
    req: CreateUserRequest,
    session: AsyncSession = Depends(get_async_session),
    _: str = Depends(verify_api_key),
):
    existing = await session.scalar(
        select(func.count()).select_from(AdminUser).where(AdminUser.email == req.email)
    )
    if existing:
        raise HTTPException(status_code=409, detail="Email already exists")

    password_hash = bcrypt.hashpw(req.password.encode(), bcrypt.gensalt()).decode()
    user = AdminUser(
        id=uuid.uuid4(),
        email=req.email,
        password_hash=password_hash,
        display_name=req.display_name,
        role=req.role,
    )
    session.add(user)
    await session.commit()
    return {"id": str(user.id), "status": "created"}


@router.delete("/users/{user_id}")
async def delete_user(
    user_id: str,
    session: AsyncSession = Depends(get_async_session),
    _: str = Depends(verify_api_key),
):
    try:
        uid = uuid.UUID(user_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid user_id")

    user = await session.get(AdminUser, uid)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    await session.delete(user)
    await session.commit()
    return {"deleted": True, "id": user_id}
