"""Pydantic v2 schemas for TestScript and TestScriptVersion."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.models.test_script import ScriptFormat, ScriptStatus


# ---------------------------------------------------------------------------
# TestScript
# ---------------------------------------------------------------------------


class TestScriptBase(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    description: str | None = None
    format: ScriptFormat = ScriptFormat.PLAYWRIGHT_TS


class TestScriptCreate(TestScriptBase):
    requirement_id: uuid.UUID
    # Manual creation: provide the script body directly
    script_content: str | None = None


class TestScriptUpdate(BaseModel):
    title: str | None = Field(None, min_length=1, max_length=500)
    description: str | None = None
    format: ScriptFormat | None = None


class TestScriptResponse(TestScriptBase):
    id: uuid.UUID
    tenant_id: uuid.UUID
    project_id: uuid.UUID
    requirement_id: uuid.UUID
    status: ScriptStatus
    cosmos_doc_id: str | None
    current_version: int
    is_ai_generated: bool
    approved_by: uuid.UUID | None
    created_by: uuid.UUID
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ApprovalRequest(BaseModel):
    comments: str | None = None


class RejectionRequest(BaseModel):
    comments: str = Field(min_length=1, max_length=2000)


class ExportRequest(BaseModel):
    format: ScriptFormat
    include_data_table: bool = False


class ExportResponse(BaseModel):
    format: ScriptFormat
    content: str
    blob_uri: str | None = None
    download_url: str | None = None
    expires_at: datetime | None = None
    validation_errors: list[str] = []


class BulkExportRequest(BaseModel):
    script_ids: list[uuid.UUID] = Field(min_length=1, max_length=50)
    format: ScriptFormat
    project_name: str = "KAATS"
    system_url: str = ""


class BulkExportResponse(BaseModel):
    format: ScriptFormat
    blob_uri: str | None
    download_url: str | None
    expires_at: datetime | None
    file_count: int
    generated_at: datetime


# ---------------------------------------------------------------------------
# TestScriptVersion
# ---------------------------------------------------------------------------


class TestScriptVersionResponse(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    script_id: uuid.UUID
    version_number: int
    cosmos_doc_id: str
    change_summary: str | None
    is_ai_generated: bool
    created_by: uuid.UUID
    created_at: datetime

    model_config = {"from_attributes": True}


# Backward-compat alias
TestScriptRead = TestScriptResponse
