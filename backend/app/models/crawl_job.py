"""CrawlJob and CrawlPage models.

Crawl jobs previously reused the generic Job table. They now have their own
dedicated tables so that crawl-specific fields (crawler_type, target_url,
auth config, page inventory) are first-class columns rather than JSON blobs.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum

from sqlalchemy import UUID, Boolean, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import TenantAwareBase


class CrawlerType(str, Enum):
    WEB = "WEB"
    SAP_FIORI = "SAP_FIORI"


class CrawlAuthType(str, Enum):
    FORM = "form"
    BASIC = "basic"
    SAML = "saml"
    COOKIE = "cookie"
    NONE = "none"


class CrawlJobStatus(str, Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class CrawlJob(TenantAwareBase):
    """
    Tracks a single crawl run — either a BFS web crawler or SAP Fiori discovery.

    Created by the API; published to the 'crawl-jobs' Service Bus topic;
    processed by the Worker; updated with status + page inventory.
    """

    __tablename__ = "crawl_jobs"
    __table_args__ = (
        Index("ix_crawl_jobs_tenant_created", "tenant_id", "created_at"),
    )

    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id"), nullable=False, index=True
    )
    crawler_type: Mapped[CrawlerType] = mapped_column(
        String(20), nullable=False
    )
    status: Mapped[CrawlJobStatus] = mapped_column(
        String(20), nullable=False, default=CrawlJobStatus.PENDING, index=True
    )
    # WEB crawler: entry point URL
    target_url: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    # SAP Fiori crawler: launchpad URL
    launchpad_url: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    max_pages: Mapped[int] = mapped_column(Integer, nullable=False, default=50)
    auth_type: Mapped[CrawlAuthType] = mapped_column(
        String(20), nullable=False, default=CrawlAuthType.NONE
    )
    # JSON: {username, password_secret_ref, form_selectors, cookies}
    auth_config: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Auth credential config JSON — never store plain passwords; use secret ref.",
    )
    generate_scripts: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True,
        comment="If True, trigger AI script generation for each discovered page.",
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
    pages_found: Mapped[int | None] = mapped_column(Integer, nullable=True)
    scripts_generated: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    project: Mapped["Project"] = relationship(
        "Project", back_populates="crawl_jobs"
    )
    pages: Mapped[list["CrawlPage"]] = relationship(
        "CrawlPage", back_populates="crawl_job", cascade="all, delete-orphan"
    )


class CrawlPage(TenantAwareBase):
    """
    Individual page or tile-group discovered during a crawl run.

    Each CrawlPage may spawn a TestScript (via AI generation).
    The page_hash deduplicates structurally identical pages within a project.
    """

    __tablename__ = "crawl_pages"
    __table_args__ = (
        Index("ix_crawl_pages_tenant_created", "tenant_id", "created_at"),
    )

    crawl_job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("crawl_jobs.id"), nullable=False, index=True
    )
    url: Mapped[str] = mapped_column(
        String(2000), nullable=False, comment="Canonical URL or SAP Fiori tile URL."
    )
    title: Mapped[str | None] = mapped_column(String(500), nullable=True)
    page_hash: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
        index=True,
        comment="SHA-256 of the normalised DOM skeleton — used for dedup.",
    )
    depth: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # JSON list of discovered interactive element descriptors
    elements_json: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="JSON array of {selector, tag, text, role} element descriptors.",
    )
    screenshot_uri: Mapped[str | None] = mapped_column(
        String(1000), nullable=True, comment="Blob URI of page screenshot."
    )
    # Linked test script generated from this page
    generated_script_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("test_scripts.id"), nullable=True
    )

    crawl_job: Mapped["CrawlJob"] = relationship(
        "CrawlJob", back_populates="pages"
    )
