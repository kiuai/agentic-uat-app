"""Project and Environment models."""

from __future__ import annotations

import uuid
from enum import Enum

from sqlalchemy import UUID, Boolean, ForeignKey, Index, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import TenantAwareBase, TimestampMixin


class ProjectStatus(str, Enum):
    ACTIVE = "ACTIVE"
    ARCHIVED = "ARCHIVED"


class SystemType(str, Enum):
    """Type of application under test — drives crawler and script-gen strategies."""

    WEB = "WEB"
    SAP_FIORI = "SAP_FIORI"
    DESKTOP = "DESKTOP"
    API = "API"
    MOBILE = "MOBILE"


class Project(TenantAwareBase):
    __tablename__ = "projects"
    __table_args__ = (
        Index("ix_projects_tenant_created", "tenant_id", "created_at"),
    )

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[ProjectStatus] = mapped_column(
        String(20), nullable=False, default=ProjectStatus.ACTIVE
    )
    system_type: Mapped[SystemType] = mapped_column(
        String(20),
        nullable=False,
        default=SystemType.WEB,
        comment="Application type — used to select crawler and AI generation strategy.",
    )
    base_url: Mapped[str | None] = mapped_column(
        String(2000),
        nullable=True,
        comment="Default entry-point URL for crawlers.",
    )
    # Extensible JSON bag: jira_project_key, ado_org, export_format, etc.
    settings: Mapped[dict | None] = mapped_column(
        JSON, nullable=True, comment="Project-level settings JSON."
    )
    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )

    environments: Mapped[list["Environment"]] = relationship(
        "Environment", back_populates="project", cascade="all, delete-orphan"
    )
    requirements: Mapped[list["Requirement"]] = relationship(
        "Requirement", back_populates="project"
    )
    jobs: Mapped[list["Job"]] = relationship("Job", back_populates="project")
    test_cycles: Mapped[list["TestCycle"]] = relationship(
        "TestCycle", back_populates="project"
    )
    crawl_jobs: Mapped[list["CrawlJob"]] = relationship(
        "CrawlJob", back_populates="project"
    )


class EnvironmentType(str, Enum):
    DEVELOPMENT = "DEV"
    QA = "QA"
    STAGING = "STAGING"
    PRODUCTION = "PROD"


class Environment(TenantAwareBase):
    __tablename__ = "environments"

    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    type: Mapped[EnvironmentType] = mapped_column(
        String(20), nullable=False, default=EnvironmentType.QA
    )
    base_url: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    requires_bpo_approval: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    gxp_mode: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="GxP mode enforces mandatory BPO approval and signed audit records.",
    )

    project: Mapped["Project"] = relationship("Project", back_populates="environments")
