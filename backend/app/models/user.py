"""User model and role-assignment join table."""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum

from sqlalchemy import UUID, Boolean, DateTime, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import TimestampMixin, TenantMixin


class RoleCode(str, Enum):
    """
    Canonical role codes used throughout the RBAC system.

    Stored as VARCHAR(10) in user_roles.role.
    Used in auth/permissions.py to resolve permission sets.
    """

    GLOBAL_ADMIN = "GADM"
    ENTERPRISE_ADMIN = "EADM"
    COMPANY_ADMIN = "CADM"
    SYSTEM_MANAGER = "SM"
    VALIDATION_LEAD = "VL"
    QA = "QA"
    VALIDATION_TESTER = "VT"
    BUSINESS_PROCESS_OWNER = "BPO"


# Backward-compat alias — existing code imports UserRole as the role enum.
UserRole = RoleCode


class User(Base, TimestampMixin):
    """
    Authenticated user. Identity comes from Azure Entra ID (MSAL PKCE).

    A user may hold multiple roles across different tenants via the
    user_roles join table. The is_global_admin flag bypasses tenant scoping
    for the Global Admin super-user.
    """

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    # Azure Entra ID object ID — stable cross-tenant identifier
    azure_oid: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
        index=True,
        comment="Azure Entra ID object ID (oid claim).",
    )
    email: Mapped[str] = mapped_column(String(320), nullable=False, index=True)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_global_admin: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="Super-user flag — bypasses tenant isolation. Only for GADM accounts.",
    )
    last_login_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    role_assignments: Mapped[list["UserRoleAssignment"]] = relationship(
        "UserRoleAssignment", back_populates="user", cascade="all, delete-orphan"
    )


class UserRoleAssignment(Base, TenantMixin):
    """
    Join table: one user may hold multiple roles within a tenant.

    For BPO, domain_code restricts the user to a single business domain.
    A user can hold at most one role per (tenant, domain_code) combination.
    """

    __tablename__ = "user_roles"
    __table_args__ = (
        UniqueConstraint(
            "user_id", "tenant_id", "role", "domain_code",
            name="uq_user_roles_user_tenant_role_domain",
        ),
        Index("ix_user_roles_tenant_created", "tenant_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )
    role: Mapped[RoleCode] = mapped_column(
        String(10),
        nullable=False,
        comment="Role code from RoleCode enum.",
    )
    # NULL for roles that aren't domain-scoped; set for BPO assignments
    domain_code: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        comment="Business domain code — only relevant for BPO role.",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.utcnow(),
        nullable=False,
    )
    assigned_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )

    user: Mapped["User"] = relationship(
        "User", back_populates="role_assignments", foreign_keys=[user_id]
    )
