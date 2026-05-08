"""Pydantic v2 schemas for Requirement."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.models.requirement import RequirementPriority, RequirementSourceType, RequirementStatus


class RequirementBase(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    description: str | None = None
    source_type: RequirementSourceType = RequirementSourceType.TEXT
    source_ref: str | None = Field(None, max_length=500)
    content_text: str | None = None
    business_domain: str | None = Field(None, max_length=100)
    priority: RequirementPriority = RequirementPriority.MEDIUM
    tags: list[str] = []


class RequirementCreate(RequirementBase):
    pass


class RequirementUpdate(BaseModel):
    title: str | None = Field(None, min_length=1, max_length=500)
    description: str | None = None
    business_domain: str | None = None
    priority: RequirementPriority | None = None
    tags: list[str] | None = None
    status: RequirementStatus | None = None


class RequirementResponse(RequirementBase):
    id: uuid.UUID
    tenant_id: uuid.UUID
    project_id: uuid.UUID
    status: RequirementStatus
    blob_uri: str | None
    uploaded_by: uuid.UUID
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# Backward-compat alias
RequirementRead = RequirementResponse
