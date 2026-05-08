"""Defect model."""

from __future__ import annotations

import uuid
from enum import Enum

from sqlalchemy import UUID, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import TenantAwareBase


class DefectSeverity(str, Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class DefectStatus(str, Enum):
    OPEN = "OPEN"
    IN_PROGRESS = "IN_PROGRESS"
    RESOLVED = "RESOLVED"
    CLOSED = "CLOSED"
    WONT_FIX = "WONT_FIX"


class Defect(TenantAwareBase):
    __tablename__ = "defects"
    __table_args__ = (
        Index("ix_defects_tenant_created", "tenant_id", "created_at"),
    )

    test_result_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("test_results.id"), nullable=False, index=True
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    severity: Mapped[DefectSeverity] = mapped_column(
        String(20), nullable=False, default=DefectSeverity.MEDIUM
    )
    status: Mapped[DefectStatus] = mapped_column(
        String(20), nullable=False, default=DefectStatus.OPEN
    )
    external_ref: Mapped[str | None] = mapped_column(
        String(500), nullable=True, comment="Jira issue key or ADO work item ID."
    )
    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )

    test_result: Mapped["TestResult"] = relationship(
        "TestResult", back_populates="defects"
    )
