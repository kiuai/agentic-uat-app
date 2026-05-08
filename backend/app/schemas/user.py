"""Pydantic v2 schemas for User and UserRoleAssignment."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field

from app.models.user import RoleCode


# ---------------------------------------------------------------------------
# UserRoleAssignment
# ---------------------------------------------------------------------------


class RoleAssignmentCreate(BaseModel):
    role: RoleCode
    domain_code: str | None = Field(None, max_length=100)


class RoleAssignmentResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    tenant_id: uuid.UUID
    role: RoleCode
    domain_code: str | None
    assigned_by: uuid.UUID | None
    created_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# User
# ---------------------------------------------------------------------------


class UserBase(BaseModel):
    email: EmailStr
    display_name: str = Field(min_length=1, max_length=255)
    is_active: bool = True


class UserCreate(UserBase):
    azure_oid: str = Field(min_length=1, max_length=255)
    # Initial role assignment within the calling tenant
    role: RoleCode = RoleCode.VALIDATION_TESTER
    domain_code: str | None = None


class UserUpdate(BaseModel):
    display_name: str | None = Field(None, min_length=1, max_length=255)
    is_active: bool | None = None


class UserResponse(UserBase):
    id: uuid.UUID
    azure_oid: str
    is_global_admin: bool
    last_login_at: datetime | None
    created_at: datetime
    updated_at: datetime
    # Roles within the current tenant context (injected by service layer)
    roles: list[RoleAssignmentResponse] = []

    model_config = {"from_attributes": True}


# Backward-compat alias
UserRead = UserResponse
