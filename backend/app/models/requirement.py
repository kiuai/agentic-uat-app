"""Requirement model."""

from __future__ import annotations

import uuid
from enum import Enum

from sqlalchemy import UUID, ForeignKey, Index, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import TenantAwareBase


class RequirementSourceType(str, Enum):
    TEXT = "TEXT"
    DOCX = "DOCX"
    PDF = "PDF"
    JIRA = "JIRA"
    ADO = "ADO"


class RequirementStatus(str, Enum):
    PENDING = "PENDING"
    PROCESSED = "PROCESSED"
    FAILED = "FAILED"


class RequirementPriority(str, Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class Requirement(TenantAwareBase):
    __tablename__ = "requirements"
    __table_args__ = (
        Index("ix_requirements_tenant_created", "tenant_id", "created_at"),
    )

    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Full requirement narrative — used as AI generation context.",
    )
    source_type: Mapped[RequirementSourceType] = mapped_column(
        String(20), nullable=False, default=RequirementSourceType.TEXT
    )
    source_ref: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
        comment="External reference, e.g. Jira issue key or ADO work item ID.",
    )
    content_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    blob_uri: Mapped[str | None] = mapped_column(
        String(1000),
        nullable=True,
        comment="Original file URI in Azure Blob Storage.",
    )
    status: Mapped[RequirementStatus] = mapped_column(
        String(20), nullable=False, default=RequirementStatus.PENDING
    )
    # Business domain code — used for BPO scoping and domain-level reports
    business_domain: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        index=True,
        comment="Business domain code, matches business_domains.code.",
    )
    priority: Mapped[RequirementPriority] = mapped_column(
        String(20),
        nullable=False,
        default=RequirementPriority.MEDIUM,
    )
    # JSON array of freeform tags, e.g. ["regression", "smoke", "gxp"]
    tags: Mapped[list | None] = mapped_column(
        JSON, nullable=True, comment="Freeform tag list for filtering."
    )
    uploaded_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )

    project: Mapped["Project"] = relationship("Project", back_populates="requirements")
    test_scripts: Mapped[list["TestScript"]] = relationship(
        "TestScript", back_populates="requirement"
    )
