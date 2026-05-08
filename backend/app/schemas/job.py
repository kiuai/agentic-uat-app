"""Pydantic v2 schemas for Job."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel

from app.models.job import JobStatus, JobType


class JobResponse(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    project_id: uuid.UUID
    job_type: JobType
    status: JobStatus
    created_by: uuid.UUID
    started_at: datetime | None
    completed_at: datetime | None
    error_message: str | None
    cosmos_result_id: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# Backward-compat alias
JobRead = JobResponse

__all__ = ["JobResponse", "JobRead", "JobStatus", "JobType"]
