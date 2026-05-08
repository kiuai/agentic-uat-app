"""
Pytest configuration and fixtures.

Uses an in-memory SQLite database for unit tests to avoid needing
a running SQL Server instance. Integration tests use the real SQL Server
container (set INTEGRATION_TEST=1 to run them).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.auth.azure_ad import CurrentUser, TenantContext
from app.auth.permissions import ROLE_PERMISSIONS, Permission
from app.database import Base
from app.models.tenant import Company, Enterprise
from app.models.user import RoleCode, User, UserRoleAssignment


# ---------------------------------------------------------------------------
# Database fixtures
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Tenant and user fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def tenant_id() -> uuid.UUID:
    return uuid.UUID("11111111-1111-1111-1111-111111111111")


@pytest.fixture
def enterprise_id() -> uuid.UUID:
    return uuid.UUID("22222222-2222-2222-2222-222222222222")


@pytest.fixture
def mock_enterprise(enterprise_id: uuid.UUID) -> Enterprise:
    e = Enterprise.__new__(Enterprise)
    e.id = enterprise_id
    e.name = "Test Enterprise"
    e.slug = "test-enterprise"
    e.is_active = True
    e.azure_ad_tenant_id = None
    e.settings = None
    return e


@pytest.fixture
def mock_company(tenant_id: uuid.UUID, enterprise_id: uuid.UUID) -> Company:
    c = Company.__new__(Company)
    c.id = tenant_id
    c.tenant_id = tenant_id
    c.enterprise_id = enterprise_id
    c.name = "Test Company"
    c.slug = "test-company"
    c.is_active = True
    c.settings = None
    return c


def _make_current_user(
    role: RoleCode,
    *,
    tenant_id: uuid.UUID,
    company: Company,
    enterprise: Enterprise,
    is_global_admin: bool = False,
    domain_code: str | None = None,
) -> CurrentUser:
    user_id = uuid.uuid4()
    user = User.__new__(User)
    user.id = user_id
    user.azure_oid = str(uuid.uuid4())
    user.email = f"{role.value.lower()}@test.com"
    user.display_name = f"Test {role.value}"
    user.is_active = True
    user.is_global_admin = is_global_admin
    user.last_login_at = None

    ra = UserRoleAssignment.__new__(UserRoleAssignment)
    ra.id = uuid.uuid4()
    ra.user_id = user_id
    ra.tenant_id = tenant_id
    ra.role = role.value
    ra.domain_code = domain_code
    ra.assigned_by = None

    tenant_ctx = TenantContext(company=company, enterprise=enterprise)
    permissions = CurrentUser.build_permissions([ra], is_global_admin)

    return CurrentUser(
        user=user,
        tenant_ctx=tenant_ctx,
        role_assignments=[ra],
        _permissions=permissions,
    )


@pytest.fixture
def admin_user(
    tenant_id: uuid.UUID, mock_company: Company, mock_enterprise: Enterprise
) -> CurrentUser:
    return _make_current_user(
        RoleCode.COMPANY_ADMIN,
        tenant_id=tenant_id,
        company=mock_company,
        enterprise=mock_enterprise,
    )


@pytest.fixture
def vt_user(
    tenant_id: uuid.UUID, mock_company: Company, mock_enterprise: Enterprise
) -> CurrentUser:
    return _make_current_user(
        RoleCode.VALIDATION_TESTER,
        tenant_id=tenant_id,
        company=mock_company,
        enterprise=mock_enterprise,
    )


@pytest.fixture
def global_admin_user(
    tenant_id: uuid.UUID, mock_company: Company, mock_enterprise: Enterprise
) -> CurrentUser:
    return _make_current_user(
        RoleCode.GLOBAL_ADMIN,
        tenant_id=tenant_id,
        company=mock_company,
        enterprise=mock_enterprise,
        is_global_admin=True,
    )


# ---------------------------------------------------------------------------
# HTTP client fixture
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def async_client(admin_user: CurrentUser) -> AsyncGenerator[AsyncClient, None]:
    from app.dependencies import get_current_user, get_tenant_db
    from app.main import create_app

    test_app = create_app()

    async def override_auth() -> CurrentUser:
        return admin_user

    async def override_db() -> AsyncGenerator[AsyncSession, None]:
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        factory = async_sessionmaker(
            bind=engine, class_=AsyncSession, expire_on_commit=False
        )
        async with factory() as session:
            yield session

    test_app.dependency_overrides[get_current_user] = override_auth
    test_app.dependency_overrides[get_tenant_db] = override_db

    async with AsyncClient(
        transport=ASGITransport(app=test_app), base_url="http://test"
    ) as client:
        yield client
