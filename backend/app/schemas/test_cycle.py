"""Pydantic v2 schemas for TestCycle, TestAssignment, TestResult, and ExecutionEvidence."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, Field

from app.models.test_cycle import CycleStatus, ExecutionStatus


# ---------------------------------------------------------------------------
# TestCycle
# ---------------------------------------------------------------------------


class TestCycleBase(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None
    planned_start_date: date | None = None
    planned_end_date: date | None = None


class TestCycleCreate(TestCycleBase):
    environment_id: uuid.UUID
    lead_user_id: uuid.UUID | None = None


class TestCycleUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = None
    lead_user_id: uuid.UUID | None = None
    planned_start_date: date | None = None
    planned_end_date: date | None = None
    actual_start_date: date | None = None
    actual_end_date: date | None = None
    status: CycleStatus | None = None


class TestCycleResponse(TestCycleBase):
    id: uuid.UUID
    tenant_id: uuid.UUID
    project_id: uuid.UUID
    environment_id: uuid.UUID
    status: CycleStatus
    created_by: uuid.UUID
    lead_user_id: uuid.UUID | None
    actual_start_date: date | None
    actual_end_date: date | None
    bpo_approved_by: uuid.UUID | None
    bpo_approved_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# TestAssignment
# ---------------------------------------------------------------------------


class TestAssignmentCreate(BaseModel):
    script_id: uuid.UUID
    script_version: int = Field(ge=1)
    assigned_to: uuid.UUID
    due_date: date | None = None
    notes: str | None = None


class TestAssignmentUpdate(BaseModel):
    status: ExecutionStatus | None = None
    notes: str | None = None
    due_date: date | None = None


class TestAssignmentResponse(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    cycle_id: uuid.UUID
    script_id: uuid.UUID
    script_version: int
    assigned_to: uuid.UUID
    assigned_by: uuid.UUID
    status: ExecutionStatus
    due_date: date | None
    notes: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# TestResult
# ---------------------------------------------------------------------------


class TestResultCreate(BaseModel):
    status: ExecutionStatus
    executed_at: datetime
    duration_seconds: int | None = None
    notes: str | None = None
    step_results: list[dict[str, Any]] = []


class TestResultResponse(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    assignment_id: uuid.UUID
    status: ExecutionStatus
    executed_by: uuid.UUID
    executed_at: datetime
    duration_seconds: int | None
    notes: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# ExecutionEvidence
# ---------------------------------------------------------------------------


class EvidenceResponse(BaseModel):
    id: uuid.UUID
    result_id: uuid.UUID
    blob_uri: str
    file_name: str
    content_type: str | None
    uploaded_by: uuid.UUID
    uploaded_at: datetime

    model_config = {"from_attributes": True}


# Backward-compat aliases
TestCycleRead = TestCycleResponse
ExecutionCreate = TestAssignmentCreate
ExecutionUpdate = TestAssignmentUpdate
ExecutionRead = TestAssignmentResponse
EvidenceRead = EvidenceResponse
