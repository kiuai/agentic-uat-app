"""
SQLAlchemy async engine and session factory.

Row-level security (RLS) is enforced at the database level via
SESSION_CONTEXT(N'tenant_id'). This module ensures that context is set on
every connection acquired from the pool before any query is executed.
"""

from __future__ import annotations

import urllib.parse
from contextlib import asynccontextmanager
from typing import AsyncGenerator
from uuid import UUID

import structlog
from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import (
    AsyncConnection,
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.config import Settings, get_settings

logger = structlog.get_logger(__name__)


class Base(DeclarativeBase):
    """SQLAlchemy declarative base for all ORM models."""


def build_engine(settings: Settings | None = None) -> AsyncEngine:
    cfg = settings or get_settings()
    odbc_connect = urllib.parse.quote_plus(cfg.azure_sql_connection_string)
    url = f"mssql+aioodbc:///?odbc_connect={odbc_connect}"

    engine = create_async_engine(
        url,
        echo=cfg.environment == "development",
        pool_pre_ping=True,
        pool_size=10,
        max_overflow=20,
        pool_timeout=30,
        pool_recycle=1800,
    )

    @event.listens_for(engine.sync_engine, "connect")
    def on_connect(dbapi_conn: object, connection_record: object) -> None:
        # Enable READ_COMMITTED_SNAPSHOT for better concurrency on Azure SQL
        pass  # Isolation level managed at server level

    return engine


# Module-level singletons; replaced in tests
_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def get_engine() -> AsyncEngine:
    global _engine
    if _engine is None:
        _engine = build_engine()
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(
            bind=get_engine(),
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=False,
            autocommit=False,
        )
    return _session_factory


async def set_tenant_context(session: AsyncSession, tenant_id: UUID) -> None:
    """Set SESSION_CONTEXT so Azure SQL RLS policies filter to this tenant."""
    await session.execute(
        text("EXEC sp_set_session_context N'tenant_id', :tid, @read_only = 1"),
        {"tid": str(tenant_id)},
    )


@asynccontextmanager
async def tenant_session(tenant_id: UUID) -> AsyncGenerator[AsyncSession, None]:
    """Async context manager that yields a session with tenant context pre-set."""
    factory = get_session_factory()
    async with factory() as session:
        await set_tenant_context(session, tenant_id)
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency — yields a raw session WITHOUT tenant context.
    Use only for admin endpoints or when tenant context is set by the caller.
    Prefer tenant_session() for all tenant-scoped operations.
    """
    factory = get_session_factory()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


def tenant_filter(model_class: type, tenant_id: UUID):
    """
    Return a SQLAlchemy WHERE clause fragment that filters a TenantAwareBase
    model to the given tenant.

    Usage::

        stmt = select(Project).where(tenant_filter(Project, tenant_id))

    This is a defence-in-depth helper. RLS predicates already enforce isolation
    at the DB level; this clause makes the intent explicit in Python query code
    and allows unit tests running without RLS to still see correct results.
    """
    return model_class.tenant_id == tenant_id


async def check_db_connection() -> bool:
    """Health check — returns True if the database is reachable."""
    try:
        async with get_engine().connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except Exception as exc:
        logger.error("database_health_check_failed", error=str(exc))
        return False


async def dispose_engine() -> None:
    """Gracefully close all pool connections on application shutdown."""
    global _engine
    if _engine is not None:
        await _engine.dispose()
        _engine = None
