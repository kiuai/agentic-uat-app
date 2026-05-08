"""GlobalConfig — system-wide key/value settings managed by Global Admins."""

from __future__ import annotations

import uuid

from sqlalchemy import UUID, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.base import TimestampMixin


class GlobalConfig(Base, TimestampMixin):
    """
    System-wide configuration entries.

    Examples: default AI model, max pages per crawl, feature flags.
    Only GADM role may read or mutate these rows.
    """

    __tablename__ = "global_config"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    key: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
        index=True,
        comment="Unique configuration key, e.g. 'ai.default_model'.",
    )
    value: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="JSON-encoded or plain-text value.",
    )
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_secret: Mapped[bool] = mapped_column(
        default=False,
        nullable=False,
        comment="When True, value is redacted in API responses.",
    )
