"""Pydantic v2 schemas for CrawlJob and CrawlPage."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.models.crawl_job import CrawlAuthType, CrawlJobStatus, CrawlerType


# ---------------------------------------------------------------------------
# CrawlJob
# ---------------------------------------------------------------------------


class CrawlJobCreate(BaseModel):
    crawler_type: CrawlerType = CrawlerType.WEB
    target_url: str | None = Field(None, max_length=2000)
    launchpad_url: str | None = Field(None, max_length=2000)
    max_pages: int = Field(50, ge=1, le=500)
    auth_type: CrawlAuthType = CrawlAuthType.NONE
    generate_scripts: bool = True


class CrawlJobResponse(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    project_id: uuid.UUID
    crawler_type: CrawlerType
    status: CrawlJobStatus
    target_url: str | None
    launchpad_url: str | None
    max_pages: int
    auth_type: CrawlAuthType
    generate_scripts: bool
    created_by: uuid.UUID
    started_at: datetime | None
    completed_at: datetime | None
    pages_found: int | None
    scripts_generated: int | None
    error_message: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# CrawlPage
# ---------------------------------------------------------------------------


class CrawlPageResponse(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    crawl_job_id: uuid.UUID
    url: str
    title: str | None
    page_hash: str | None
    depth: int
    screenshot_uri: str | None
    generated_script_id: uuid.UUID | None
    created_at: datetime

    model_config = {"from_attributes": True}
