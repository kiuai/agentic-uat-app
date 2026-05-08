"""Enterprise, Company, and BusinessDomain models."""

from __future__ import annotations

import uuid

from sqlalchemy import UUID, Boolean, ForeignKey, JSON, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import TimestampMixin


class Enterprise(Base, TimestampMixin):
    """Top-level tenant grouping (e.g. a corporate parent with multiple subsidiaries)."""

    __tablename__ = "enterprises"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(
        String(100), unique=True, nullable=False, index=True
    )
    # Azure Entra ID tenant ID for federated SSO at enterprise level
    azure_ad_tenant_id: Mapped[str | None] = mapped_column(
        String(255),
        unique=True,
        nullable=True,
        index=True,
        comment="Azure Entra ID tenant GUID — used to map SSO logins to enterprise.",
    )
    # Extensible JSON bag: allowed_domains, max_companies, feature_flags, etc.
    settings: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
        comment="Enterprise-level settings JSON.",
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    companies: Mapped[list["Company"]] = relationship(
        "Company", back_populates="enterprise"
    )


class Company(Base, TimestampMixin):
    """
    Isolated tenant unit. tenant_id equals company.id throughout the system.

    Azure SQL RLS policies filter on SESSION_CONTEXT(N'tenant_id'), which is
    set to this company's id on every connection.
    """

    __tablename__ = "companies"
    __table_args__ = (
        UniqueConstraint("enterprise_id", "slug", name="uq_companies_enterprise_slug"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    enterprise_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("enterprises.id"), nullable=False, index=True
    )
    # tenant_id IS company.id — kept as explicit column for RLS clarity
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), unique=True, nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    # Extensible JSON bag: allowed_roles, max_users, gxp_enabled, etc.
    settings: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
        comment="Company-level settings JSON.",
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    enterprise: Mapped["Enterprise"] = relationship(
        "Enterprise", back_populates="companies"
    )
    business_domains: Mapped[list["BusinessDomain"]] = relationship(
        "BusinessDomain", back_populates="company"
    )


class BusinessDomain(Base, TimestampMixin):
    """Organisational domain grouping (e.g. Finance, HR, Supply Chain)."""

    __tablename__ = "business_domains"
    __table_args__ = (
        UniqueConstraint("tenant_id", "code", name="uq_business_domains_tenant_code"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("companies.tenant_id"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    code: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="Short code used in requirement domain_code and BPO scoping.",
    )
    description: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    company: Mapped["Company"] = relationship(
        "Company", back_populates="business_domains"
    )
