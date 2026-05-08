"""AuditLog model — immutable record of all KAATS actions."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import UUID, DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.base import TenantMixin


class AuditLog(Base, TenantMixin):
    """
    Immutable append-only log of all significant actions.
    No UPDATE or DELETE is permitted on this table at the application layer.
    """

    __tablename__ = "audit_logs"
    __table_args__ = (
        Index("ix_audit_logs_tenant_created", "tenant_id", "created_at"),
        Index("ix_audit_logs_resource", "tenant_id", "resource_type", "resource_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    action: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="CREATE, READ, UPDATE, DELETE, APPROVE, EXECUTE, LOGIN, etc.",
    )
    resource_type: Mapped[str] = mapped_column(
        String(100), nullable=False, comment="project, requirement, test_script, execution, etc."
    )
    resource_id: Mapped[str] = mapped_column(
        String(500), nullable=False, comment="UUID or Cosmos document ID."
    )
    before_state: Mapped[str | None] = mapped_column(Text, nullable=True, comment="JSON snapshot.")
    after_state: Mapped[str | None] = mapped_column(Text, nullable=True, comment="JSON snapshot.")
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.sysdatetimeoffset(),
        comment="Indexed; never updated.",
    )
