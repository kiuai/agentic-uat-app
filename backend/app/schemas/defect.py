"""Pydantic v2 schemas for Defect."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.models.defect import DefectSeverity, DefectStatus


class DefectCreate(BaseModel):
    test_result_id: uuid.UUID
    title: str = Field(min_length=1, max_length=500)
    description: str | None = None
    severity: DefectSeverity = DefectSeverity.MEDIUM


class DefectUpdate(BaseModel):
    title: str | None = Field(None, min_length=1, max_length=500)
    description: str | None = None
    severity: DefectSeverity | None = None
    status: DefectStatus | None = None
    external_ref: str | None = None


class DefectResponse(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    test_result_id: uuid.UUID
    project_id: uuid.UUID
    title: str
    description: str | None
    severity: DefectSeverity
    status: DefectStatus
    external_ref: str | None
    created_by: uuid.UUID
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# Backward-compat alias
DefectRead = DefectResponse
