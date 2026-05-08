"""Base classes for all SQLAlchemy ORM models.

TenantAwareBase — abstract base for every row-level-security-scoped table.
TimestampMixin  — standalone mixin for tables that need timestamps but no RLS
                  (e.g. GlobalConfig, AuditLog).
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import UUID, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class TimestampMixin:
    """Adds created_at and updated_at to any model (no tenant isolation)."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
        server_default=func.sysdatetimeoffset(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
        onupdate=utcnow,
        server_default=func.sysdatetimeoffset(),
        nullable=False,
    )


class TenantMixin:
    """
    Standalone tenant_id column mixin.

    Prefer TenantAwareBase for new tables. This mixin exists only to support
    tables that also need custom primary-key definitions outside the standard
    UUID pattern (e.g., audit_log append-only tables).
    """

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,
        comment="Company tenant ID — used by Azure SQL RLS FILTER predicate.",
    )


class TenantAwareBase(Base):
    """
    Abstract declarative base for every RLS-scoped table.

    Provides:
      • id          — UUID primary key, auto-generated.
      • tenant_id   — Azure SQL RLS isolation column (company.id).
      • created_at  — server-defaulted UTC timestamp.
      • updated_at  — server-defaulted, updated on every row write.

    All company-scoped tables MUST inherit from this class. Non-tenant tables
    (Enterprise, Company, GlobalConfig, AuditLog) inherit directly from Base.
    """

    __abstract__ = True

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,
        comment="Company tenant ID — RLS isolation column.",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
        server_default=func.sysdatetimeoffset(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
        onupdate=utcnow,
        server_default=func.sysdatetimeoffset(),
        nullable=False,
    )
