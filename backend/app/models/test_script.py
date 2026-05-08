"""TestScript and TestScriptVersion SQL models.

Script content (the actual generated code) is stored in Azure Cosmos DB
(container: kaats-{tenant_id}, document type: test_script). The SQL rows
act as the authoritative metadata and approval-state registry; Cosmos holds
the versioned content blobs.
"""

from __future__ import annotations

import uuid
from enum import Enum

from sqlalchemy import UUID, Boolean, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import TenantAwareBase


class ScriptStatus(str, Enum):
    DRAFT = "DRAFT"
    IN_REVIEW = "IN_REVIEW"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    LOCKED = "LOCKED"


class ScriptFormat(str, Enum):
    PLAYWRIGHT_TS = "playwright_ts"
    PLAYWRIGHT_JS = "playwright_js"
    SELENIUM_PYTHON = "selenium_python"
    PYTEST = "pytest"
    ROBOT_FRAMEWORK = "robot_framework"
    GHERKIN = "gherkin"


class TestScript(TenantAwareBase):
    """
    Metadata record for an AI-generated or manually authored test script.

    The script code body lives in Cosmos DB (cosmos_doc_id → document).
    The active_version_id pointer tells consumers which version is current.
    """

    __tablename__ = "test_scripts"
    __table_args__ = (
        Index("ix_test_scripts_tenant_created", "tenant_id", "created_at"),
    )

    requirement_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("requirements.id"), nullable=False, index=True
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    format: Mapped[ScriptFormat] = mapped_column(
        String(30), nullable=False, default=ScriptFormat.PLAYWRIGHT_TS
    )
    status: Mapped[ScriptStatus] = mapped_column(
        String(20), nullable=False, default=ScriptStatus.DRAFT, index=True
    )
    # Pointer to the active Cosmos DB document (content blob)
    cosmos_doc_id: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
        comment="Cosmos DB document ID in the tenant's kaats-{tenant_id} container.",
    )
    current_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    is_ai_generated: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    # Populated when status → APPROVED
    approved_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )

    requirement: Mapped["Requirement"] = relationship(
        "Requirement", back_populates="test_scripts"
    )
    versions: Mapped[list["TestScriptVersion"]] = relationship(
        "TestScriptVersion",
        back_populates="script",
        cascade="all, delete-orphan",
        order_by="TestScriptVersion.version_number",
    )
    assignments: Mapped[list["TestAssignment"]] = relationship(
        "TestAssignment", back_populates="script"
    )


class TestScriptVersion(TenantAwareBase):
    """
    Immutable version snapshot of a test script.

    Each AI generation run or manual edit creates a new version row.
    The script code is referenced by cosmos_doc_id; SQL stores the diff metadata.
    """

    __tablename__ = "test_script_versions"
    __table_args__ = (
        Index(
            "ix_test_script_versions_tenant_created", "tenant_id", "created_at"
        ),
    )

    script_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("test_scripts.id"), nullable=False, index=True
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    cosmos_doc_id: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
        comment="Cosmos DB document ID for this version's content.",
    )
    change_summary: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Human-readable or AI-generated description of what changed.",
    )
    is_ai_generated: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )

    script: Mapped["TestScript"] = relationship(
        "TestScript", back_populates="versions"
    )
