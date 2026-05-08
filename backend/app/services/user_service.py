"""User management service."""

from __future__ import annotations

import uuid

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.schemas.user import UserCreate, UserRead, UserUpdate


class UserService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def list_users(self, tenant_id: uuid.UUID) -> list[UserRead]:
        result = await self._db.execute(
            select(User).where(User.tenant_id == tenant_id, User.is_active == True)
        )
        return [UserRead.model_validate(u) for u in result.scalars()]

    async def get_user(self, user_id: uuid.UUID) -> UserRead:
        user = await self._db.get(User, user_id)
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")
        return UserRead.model_validate(user)

    async def create_user(self, tenant_id: uuid.UUID, body: UserCreate) -> UserRead:
        user = User(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            entra_object_id=f"pending-{uuid.uuid4()}",
            email=body.email,
            display_name=body.display_name,
            role=body.role,
            domains=body.domains,
        )
        self._db.add(user)
        await self._db.flush()
        await self._db.refresh(user)
        return UserRead.model_validate(user)

    async def update_user(self, user_id: uuid.UUID, body: UserUpdate) -> UserRead:
        user = await self._db.get(User, user_id)
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")
        if body.display_name is not None:
            user.display_name = body.display_name
        if body.role is not None:
            user.role = body.role
        if body.domains is not None:
            user.set_domains(body.domains)
        if body.is_active is not None:
            user.is_active = body.is_active
        await self._db.flush()
        await self._db.refresh(user)
        return UserRead.model_validate(user)
