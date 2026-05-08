"""
Job model — tracks async background tasks (AI generation, export, report).

Crawl jobs are now tracked by the dedicated CrawlJob + CrawlPage tables.
This generic Job table covers: AI_GENERATION, EXPORT, REPORT job types.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum

from sqlalchemy import UUID, DateTime, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import TenantAwareBase


class JobType(str, Enum):
    AI_GENERATION = "AI_GENERATION"
    EXPORT = "EXPORT"
    REPORT = "REPORT"


class JobStatus(str, Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class Job(TenantAwareBase):
    __tablename__ = "jobs"
    __table_args__ = (
        Index("ix_jobs_tenant_created", "tenant_id", "created_at"),
    )

    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id"), nullable=False, index=True
    )
    job_type: Mapped[JobType] = mapped_column(String(20), nullable=False)
    status: Mapped[JobStatus] = mapped_column(
        String(20), nullable=False, default=JobStatus.PENDING, index=True
    )
    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    # JSON payload: requirement_ids, generation_config, export_format, etc.
    input_payload: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Cosmos DB document ID of the result artifact (e.g. generated script batch)
    cosmos_result_id: Mapped[str | None] = mapped_column(String(500), nullable=True)

    project: Mapped["Project"] = relationship("Project", back_populates="jobs")
