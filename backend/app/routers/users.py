"""User management endpoints."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, status

from app.dependencies import CurrentUser, TenantDB, require_roles
from app.models.user import UserRole
from app.schemas.user import UserCreate, UserRead, UserUpdate
from app.services.user_service import UserService

router = APIRouter(prefix="/users")


@router.get("", response_model=list[UserRead])
async def list_users(
    db: TenantDB,
    current_user: CurrentUser,
) -> list[UserRead]:
    service = UserService(db)
    return await service.list_users(current_user.tenant_id)


@router.get("/{user_id}", response_model=UserRead)
async def get_user(user_id: uuid.UUID, db: TenantDB) -> UserRead:
    service = UserService(db)
    return await service.get_user(user_id)


@router.post(
    "",
    response_model=UserRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_roles(UserRole.GADM, UserRole.EADM, UserRole.CADM))],
)
async def create_user(
    body: UserCreate, db: TenantDB, current_user: CurrentUser
) -> UserRead:
    service = UserService(db)
    return await service.create_user(current_user.tenant_id, body)


@router.patch(
    "/{user_id}",
    response_model=UserRead,
    dependencies=[Depends(require_roles(UserRole.GADM, UserRole.EADM, UserRole.CADM))],
)
async def update_user(
    user_id: uuid.UUID, body: UserUpdate, db: TenantDB
) -> UserRead:
    service = UserService(db)
    return await service.update_user(user_id, body)
