"""
Pytest configuration and fixtures.

Uses an in-memory SQLite database for unit tests to avoid needing
a running SQL Server instance. Integration tests use the real SQL Server
container (set INTEGRATION_TEST=1 to run them).
"""

from __future__ import annotations

import os
import uuid
from typing import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.database import Base
from app.models.user import User, UserRole


# ── Database fixtures ─────────────────────────────────────────────────────────

@pytest_asyncio.fixture(scope="session")
async def test_engine():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(test_engine) -> AsyncGenerator[AsyncSession, None]:
    session_factory = async_sessionmaker(
        bind=test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )
    async with session_factory() as session:
        yield session
        await session.rollback()


# ── Auth fixtures ─────────────────────────────────────────────────────────────

@pytest.fixture
def tenant_id() -> uuid.UUID:
    return uuid.UUID("11111111-1111-1111-1111-111111111111")


@pytest.fixture
def admin_user(tenant_id: uuid.UUID) -> User:
    return User(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        entra_object_id=str(uuid.uuid4()),
        email="admin@test.com",
        display_name="Test Admin",
        role=UserRole.COMPANY_ADMIN,
        is_active=True,
    )


@pytest.fixture
def vt_user(tenant_id: uuid.UUID) -> User:
    return User(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        entra_object_id=str(uuid.uuid4()),
        email="tester@test.com",
        display_name="Test Tester",
        role=UserRole.VALIDATION_TESTER,
        is_active=True,
    )


# ── HTTP client fixture ───────────────────────────────────────────────────────

@pytest_asyncio.fixture
async def async_client(admin_user: User) -> AsyncGenerator[AsyncClient, None]:
    from app.main import create_app
    from app.dependencies import get_current_user, get_tenant_db

    test_app = create_app()

    async def override_auth() -> User:
        return admin_user

    async def override_db() -> AsyncGenerator[AsyncSession, None]:
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
        async with factory() as session:
            yield session

    test_app.dependency_overrides[get_current_user] = override_auth
    test_app.dependency_overrides[get_tenant_db] = override_db

    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
        yield client
