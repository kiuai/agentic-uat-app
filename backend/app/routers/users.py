"""User management endpoints."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel, EmailStr, Field

from app.auth.permissions import Permission
from app.dependencies import CurrentUser, CurrentUserDep, RequirePermission, TenantDB
from app.models.user import RoleCode
from app.schemas.user import (
    RoleAssignmentCreate,
    RoleAssignmentResponse,
    UserCreate,
    UserResponse,
    UserUpdate,
)
from app.services.user_service import UserService

router = APIRouter(prefix="/users")


# ── List / Get ────────────────────────────────────────────────────────────────

@router.get(
    "",
    response_model=list[UserResponse],
    dependencies=[Depends(RequirePermission(Permission.USER_READ))],
)
async def list_users(
    db: TenantDB,
    current_user: CurrentUserDep,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> list[UserResponse]:
    service = UserService(db)
    return await service.list_users(current_user.tenant_id, limit=limit, offset=offset)


@router.get(
    "/{user_id}",
    response_model=UserResponse,
    dependencies=[Depends(RequirePermission(Permission.USER_READ))],
)
async def get_user(
    user_id: uuid.UUID, db: TenantDB, current_user: CurrentUserDep
) -> UserResponse:
    service = UserService(db)
    return await service.get_user(user_id, current_user.tenant_id)


# ── Create ────────────────────────────────────────────────────────────────────

@router.post(
    "",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(RequirePermission(Permission.USER_CREATE))],
)
async def create_user(
    body: UserCreate, db: TenantDB, current_user: CurrentUserDep
) -> UserResponse:
    service = UserService(db)
    return await service.create_user(current_user.tenant_id, body, current_user.id)


# ── Invite ────────────────────────────────────────────────────────────────────

class InviteRequest(BaseModel):
    email: EmailStr
    display_name: str = Field(min_length=1, max_length=255)
    role: RoleCode = RoleCode.VALIDATION_TESTER
    domain_code: str | None = None


@router.post(
    "/invite",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(RequirePermission(Permission.USER_CREATE))],
    summary="Invite a user by email; creates a pending account until first SSO login",
)
async def invite_user(
    body: InviteRequest, db: TenantDB, current_user: CurrentUserDep
) -> dict:
    service = UserService(db)
    return await service.invite_user(
        current_user.tenant_id,
        body.email,
        body.display_name,
        body.role,
        body.domain_code,
        current_user.id,
    )


# ── Update / Deactivate ───────────────────────────────────────────────────────

@router.patch(
    "/{user_id}",
    response_model=UserResponse,
    dependencies=[Depends(RequirePermission(Permission.USER_UPDATE))],
)
async def update_user(
    user_id: uuid.UUID, body: UserUpdate, db: TenantDB
) -> UserResponse:
    service = UserService(db)
    return await service.update_user(user_id, body)


@router.post(
    "/{user_id}/deactivate",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(RequirePermission(Permission.USER_DELETE))],
)
async def deactivate_user(user_id: uuid.UUID, db: TenantDB) -> None:
    service = UserService(db)
    await service.deactivate_user(user_id)


# ── Role Assignments ──────────────────────────────────────────────────────────

@router.get(
    "/{user_id}/roles",
    response_model=list[RoleAssignmentResponse],
    dependencies=[Depends(RequirePermission(Permission.USER_READ))],
)
async def list_user_roles(
    user_id: uuid.UUID, db: TenantDB, current_user: CurrentUserDep
) -> list[RoleAssignmentResponse]:
    service = UserService(db)
    return await service.list_roles(user_id, current_user.tenant_id)


@router.post(
    "/{user_id}/roles",
    response_model=RoleAssignmentResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(RequirePermission(Permission.USER_ASSIGN_ROLE))],
)
async def assign_role(
    user_id: uuid.UUID,
    body: RoleAssignmentCreate,
    db: TenantDB,
    current_user: CurrentUserDep,
) -> RoleAssignmentResponse:
    service = UserService(db)
    return await service.assign_role(user_id, current_user.tenant_id, body, current_user.id)


@router.delete(
    "/{user_id}/roles/{role}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(RequirePermission(Permission.USER_ASSIGN_ROLE))],
)
async def revoke_role(
    user_id: uuid.UUID,
    role: RoleCode,
    db: TenantDB,
    current_user: CurrentUserDep,
    domain_code: str | None = Query(None),
) -> None:
    service = UserService(db)
    await service.revoke_role(user_id, current_user.tenant_id, role, domain_code)
