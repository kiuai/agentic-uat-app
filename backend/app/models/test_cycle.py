"""TestCycle, TestAssignment, TestResult, and ExecutionEvidence models."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from enum import Enum

from sqlalchemy import UUID, Boolean, Date, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import TenantAwareBase, TimestampMixin, TenantMixin
from app.database import Base


class CycleStatus(str, Enum):
    DRAFT = "DRAFT"
    ACTIVE = "ACTIVE"
    COMPLETED = "COMPLETED"
    LOCKED = "LOCKED"


class ExecutionStatus(str, Enum):
    NOT_STARTED = "NOT_STARTED"
    IN_PROGRESS = "IN_PROGRESS"
    PASSED = "PASSED"
    FAILED = "FAILED"
    BLOCKED = "BLOCKED"
    SKIPPED = "SKIPPED"


class TestCycle(TenantAwareBase):
    """
    A time-boxed testing campaign containing assignments of test scripts to testers.

    GxP cycles require BPO approval before status → LOCKED.
    """

    __tablename__ = "test_cycles"
    __table_args__ = (
        Index("ix_test_cycles_tenant_created", "tenant_id", "created_at"),
    )

    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id"), nullable=False, index=True
    )
    environment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("environments.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[CycleStatus] = mapped_column(
        String(20), nullable=False, default=CycleStatus.DRAFT
    )
    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    lead_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=True,
        comment="Validation Lead responsible for this cycle.",
    )
    # Planned dates (set at cycle creation)
    planned_start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    planned_end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    # Actual dates (populated as cycle progresses)
    actual_start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    actual_end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    # BPO approval tracking
    bpo_approved_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    bpo_approved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    project: Mapped["Project"] = relationship("Project", back_populates="test_cycles")
    assignments: Mapped[list["TestAssignment"]] = relationship(
        "TestAssignment", back_populates="cycle", cascade="all, delete-orphan"
    )


class TestAssignment(TenantAwareBase):
    """
    Assignment of a specific test-script version to a tester within a cycle.

    Replaces the old Execution table. Each assignment tracks one tester's
    run of one script version and records the outcome in TestResult.
    """

    __tablename__ = "test_assignments"
    __table_args__ = (
        Index("ix_test_assignments_tenant_created", "tenant_id", "created_at"),
    )

    cycle_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("test_cycles.id"), nullable=False, index=True
    )
    script_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("test_scripts.id"), nullable=False, index=True
    )
    # Version pinned at assignment time — immutable after assignment
    script_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    assigned_to: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    assigned_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    status: Mapped[ExecutionStatus] = mapped_column(
        String(20), nullable=False, default=ExecutionStatus.NOT_STARTED, index=True
    )
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    cycle: Mapped["TestCycle"] = relationship(
        "TestCycle", back_populates="assignments"
    )
    script: Mapped["TestScript"] = relationship(
        "TestScript", back_populates="assignments"
    )
    result: Mapped["TestResult | None"] = relationship(
        "TestResult",
        back_populates="assignment",
        uselist=False,
        cascade="all, delete-orphan",
    )


class TestResult(TenantAwareBase):
    """
    Execution outcome for a single test assignment.

    One-to-one with TestAssignment. Created when the tester submits their run.
    """

    __tablename__ = "test_results"
    __table_args__ = (
        Index("ix_test_results_tenant_created", "tenant_id", "created_at"),
    )

    assignment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("test_assignments.id"),
        nullable=False,
        unique=True,
        index=True,
    )
    status: Mapped[ExecutionStatus] = mapped_column(
        String(20), nullable=False, index=True
    )
    executed_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    executed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    duration_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    # JSON array of step-level results [{step, status, actual, expected, screenshot_uri}]
    step_results: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="JSON array of per-step execution results.",
    )

    assignment: Mapped["TestAssignment"] = relationship(
        "TestAssignment", back_populates="result"
    )
    evidence: Mapped[list["ExecutionEvidence"]] = relationship(
        "ExecutionEvidence", back_populates="result", cascade="all, delete-orphan"
    )
    defects: Mapped[list["Defect"]] = relationship(
        "Defect", back_populates="test_result"
    )


class ExecutionEvidence(Base, TenantMixin, TimestampMixin):
    """Screenshot, log, or attachment uploaded during test execution."""

    __tablename__ = "execution_evidence"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    result_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("test_results.id"),
        nullable=False,
        index=True,
    )
    blob_uri: Mapped[str] = mapped_column(String(1000), nullable=False)
    file_name: Mapped[str] = mapped_column(String(500), nullable=False)
    content_type: Mapped[str | None] = mapped_column(String(200), nullable=True)
    uploaded_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    result: Mapped["TestResult"] = relationship(
        "TestResult", back_populates="evidence"
    )
