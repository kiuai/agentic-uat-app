"""Pydantic v2 schemas for Project and Environment."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.models.project import EnvironmentType, ProjectStatus, SystemType


# ---------------------------------------------------------------------------
# Project
# ---------------------------------------------------------------------------


class ProjectBase(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None
    system_type: SystemType = SystemType.WEB
    base_url: str | None = Field(None, max_length=2000)
    settings: dict[str, Any] | None = None


class ProjectCreate(ProjectBase):
    pass


class ProjectUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = None
    system_type: SystemType | None = None
    base_url: str | None = None
    settings: dict[str, Any] | None = None
    status: ProjectStatus | None = None


class ProjectResponse(ProjectBase):
    id: uuid.UUID
    tenant_id: uuid.UUID
    status: ProjectStatus
    created_by: uuid.UUID
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Environment
# ---------------------------------------------------------------------------


class EnvironmentBase(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    type: EnvironmentType = EnvironmentType.QA
    base_url: str | None = Field(None, max_length=2000)
    requires_bpo_approval: bool = False
    gxp_mode: bool = False


class EnvironmentCreate(EnvironmentBase):
    pass


class EnvironmentUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=255)
    base_url: str | None = None
    requires_bpo_approval: bool | None = None
    gxp_mode: bool | None = None


class EnvironmentResponse(EnvironmentBase):
    id: uuid.UUID
    tenant_id: uuid.UUID
    project_id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# Backward-compat aliases
ProjectRead = ProjectResponse
EnvironmentRead = EnvironmentResponse
