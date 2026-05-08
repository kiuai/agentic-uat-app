"""User management service."""

from __future__ import annotations

import uuid
from typing import Any

import structlog
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import RoleCode, User, UserRoleAssignment
from app.schemas.user import (
    RoleAssignmentCreate,
    RoleAssignmentResponse,
    UserCreate,
    UserResponse,
    UserUpdate,
)

logger = structlog.get_logger(__name__)

# Backward-compat alias
UserRead = UserResponse


class UserService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def list_users(
        self,
        tenant_id: uuid.UUID,
        *,
        limit: int = 50,
        offset: int = 0,
    ) -> list[UserResponse]:
        stmt = (
            select(User)
            .join(UserRoleAssignment, UserRoleAssignment.user_id == User.id)
            .where(UserRoleAssignment.tenant_id == tenant_id, User.is_active == True)
            .distinct()
            .order_by(User.display_name)
            .offset(offset)
            .limit(limit)
        )
        result = await self._db.execute(stmt)
        users = result.scalars().all()
        out = []
        for u in users:
            roles = await self._load_roles(u.id, tenant_id)
            resp = UserResponse.model_validate(u)
            resp.roles = roles
            out.append(resp)
        return out

    async def get_user(self, user_id: uuid.UUID, tenant_id: uuid.UUID) -> UserResponse:
        user = await self._db.get(User, user_id)
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")
        roles = await self._load_roles(user_id, tenant_id)
        resp = UserResponse.model_validate(user)
        resp.roles = roles
        return resp

    async def create_user(self, tenant_id: uuid.UUID, body: UserCreate, assigned_by: uuid.UUID) -> UserResponse:
        # Check for existing user by email (across all tenants — email is global)
        existing = await self._db.scalar(
            select(User).where(User.email == body.email)
        )
        if existing:
            # User exists globally — just ensure they have a role in this tenant
            await self._assign_role_internal(
                existing.id, tenant_id, body.role, body.domain_code, assigned_by
            )
            roles = await self._load_roles(existing.id, tenant_id)
            resp = UserResponse.model_validate(existing)
            resp.roles = roles
            return resp

        user = User(
            id=uuid.uuid4(),
            azure_oid=body.azure_oid,
            email=body.email,
            display_name=body.display_name,
            is_active=body.is_active,
        )
        self._db.add(user)
        await self._db.flush()
        await self._db.refresh(user)

        # Create initial role assignment
        await self._assign_role_internal(
            user.id, tenant_id, body.role, body.domain_code, assigned_by
        )

        roles = await self._load_roles(user.id, tenant_id)
        resp = UserResponse.model_validate(user)
        resp.roles = roles
        return resp

    async def invite_user(
        self,
        tenant_id: uuid.UUID,
        email: str,
        display_name: str,
        role: RoleCode,
        domain_code: str | None,
        invited_by: uuid.UUID,
    ) -> dict[str, Any]:
        """
        Invite a user by email. Creates a pending User row with a placeholder
        azure_oid; the real OID is filled on first SSO login.
        """
        existing = await self._db.scalar(
            select(User).where(User.email == email)
        )
        if existing:
            # Already in the system — just add a role if needed
            await self._assign_role_internal(existing.id, tenant_id, role, domain_code, invited_by)
            return {"user_id": str(existing.id), "status": "role_assigned"}

        placeholder_oid = f"pending-invite-{uuid.uuid4()}"
        user = User(
            id=uuid.uuid4(),
            azure_oid=placeholder_oid,
            email=email,
            display_name=display_name,
            is_active=False,  # Activated on first login
        )
        self._db.add(user)
        await self._db.flush()

        await self._assign_role_internal(user.id, tenant_id, role, domain_code, invited_by)

        logger.info("user_invited", email=email, tenant_id=str(tenant_id), role=role.value)
        return {"user_id": str(user.id), "status": "invited", "email": email}

    async def update_user(self, user_id: uuid.UUID, body: UserUpdate) -> UserResponse:
        user = await self._db.get(User, user_id)
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")
        if body.display_name is not None:
            user.display_name = body.display_name
        if body.is_active is not None:
            user.is_active = body.is_active
        await self._db.flush()
        await self._db.refresh(user)
        return UserResponse.model_validate(user)

    async def deactivate_user(self, user_id: uuid.UUID) -> None:
        user = await self._db.get(User, user_id)
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")
        user.is_active = False
        await self._db.flush()

    async def assign_role(
        self,
        user_id: uuid.UUID,
        tenant_id: uuid.UUID,
        body: RoleAssignmentCreate,
        assigned_by: uuid.UUID,
    ) -> RoleAssignmentResponse:
        user = await self._db.get(User, user_id)
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")
        assignment = await self._assign_role_internal(
            user_id, tenant_id, body.role, body.domain_code, assigned_by
        )
        return RoleAssignmentResponse.model_validate(assignment)

    async def revoke_role(
        self,
        user_id: uuid.UUID,
        tenant_id: uuid.UUID,
        role: RoleCode,
        domain_code: str | None = None,
    ) -> None:
        stmt = select(UserRoleAssignment).where(
            UserRoleAssignment.user_id == user_id,
            UserRoleAssignment.tenant_id == tenant_id,
            UserRoleAssignment.role == role,
        )
        if domain_code is not None:
            stmt = stmt.where(UserRoleAssignment.domain_code == domain_code)
        existing = await self._db.scalar(stmt)
        if not existing:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Role assignment not found.",
            )
        await self._db.delete(existing)
        await self._db.flush()

    async def list_roles(
        self, user_id: uuid.UUID, tenant_id: uuid.UUID
    ) -> list[RoleAssignmentResponse]:
        return await self._load_roles(user_id, tenant_id)

    # ── Private helpers ───────────────────────────────────────────────────────

    async def _assign_role_internal(
        self,
        user_id: uuid.UUID,
        tenant_id: uuid.UUID,
        role: RoleCode,
        domain_code: str | None,
        assigned_by: uuid.UUID,
    ) -> UserRoleAssignment:
        # Check for duplicate
        stmt = select(UserRoleAssignment).where(
            UserRoleAssignment.user_id == user_id,
            UserRoleAssignment.tenant_id == tenant_id,
            UserRoleAssignment.role == role,
            UserRoleAssignment.domain_code == domain_code,
        )
        existing = await self._db.scalar(stmt)
        if existing:
            return existing

        assignment = UserRoleAssignment(
            id=uuid.uuid4(),
            user_id=user_id,
            tenant_id=tenant_id,
            role=role,
            domain_code=domain_code,
            assigned_by=assigned_by,
        )
        self._db.add(assignment)
        await self._db.flush()
        await self._db.refresh(assignment)
        return assignment

    async def _load_roles(
        self, user_id: uuid.UUID, tenant_id: uuid.UUID
    ) -> list[RoleAssignmentResponse]:
        result = await self._db.execute(
            select(UserRoleAssignment).where(
                UserRoleAssignment.user_id == user_id,
                UserRoleAssignment.tenant_id == tenant_id,
            )
        )
        return [RoleAssignmentResponse.model_validate(a) for a in result.scalars()]
