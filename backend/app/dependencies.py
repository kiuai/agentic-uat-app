"""
FastAPI dependency injection wiring.

Dependency chain for a typical tenant-scoped endpoint:

    request
      └─ get_current_user()          validates JWT, upserts User in DB
           └─ get_tenant_context()   resolves X-Tenant-Slug, loads roles
                └─ get_tenant_db()   opens session with RLS SESSION_CONTEXT
"""

from __future__ import annotations

import time
from collections import defaultdict
from typing import Annotated
from uuid import UUID

import structlog
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.azure_ad import (
    AzureADTokenValidator,
    CurrentUser,
    TenantContext,
    get_token_validator,
    get_user_role_assignments,
    resolve_tenant,
    upsert_user,
)
from app.auth.permissions import ROLE_PERMISSIONS, Permission
from app.config import Settings, get_settings
from app.cosmos import ContainerProxy, get_tenant_container
from app.database import get_session_factory, set_tenant_context
from app.models.user import RoleCode

logger = structlog.get_logger(__name__)

_bearer_scheme = HTTPBearer(auto_error=True)


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------


def settings_dep() -> Settings:
    return get_settings()


SettingsDep = Annotated[Settings, Depends(settings_dep)]


# ---------------------------------------------------------------------------
# Rate limiting (in-memory sliding window)
# ---------------------------------------------------------------------------

# {key: [(timestamp, count), ...]}
_rate_windows: dict[str, list[float]] = defaultdict(list)
_WINDOW_SECONDS = 60


def _check_rate_limit(key: str, max_requests: int) -> None:
    """
    Sliding-window rate limiter. Raises HTTP 429 if exceeded.

    Not Redis-backed — suitable for single-process dev/staging.
    For multi-replica production, swap implementation to Redis ZADD/ZCOUNT.
    """
    now = time.monotonic()
    window = _rate_windows[key]

    # Evict requests outside the window
    _rate_windows[key] = [ts for ts in window if now - ts < _WINDOW_SECONDS]

    if len(_rate_windows[key]) >= max_requests:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded. Please retry after a moment.",
            headers={"Retry-After": str(_WINDOW_SECONDS)},
        )

    _rate_windows[key].append(now)


# ---------------------------------------------------------------------------
# Raw session (no tenant context — for admin and auth endpoints)
# ---------------------------------------------------------------------------


async def get_admin_session() -> AsyncSession:
    """Yields a session WITHOUT tenant RLS context. Use for admin/auth paths only."""
    factory = get_session_factory()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


AdminSession = Annotated[AsyncSession, Depends(get_admin_session)]


# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------


async def get_current_user(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(_bearer_scheme)],
    settings: SettingsDep,
) -> CurrentUser:
    """
    Validate Bearer JWT → upsert User in DB → resolve tenant → build CurrentUser.

    Tenant is resolved from X-Tenant-Slug header.
    Returns HTTP 401 for invalid/expired tokens.
    Returns HTTP 403 if the user has no role in the requested tenant.
    Returns HTTP 404 if the tenant slug is unknown.
    """
    # ── Rate limit by IP for auth path ────────────────────────────────────
    client_ip = request.client.host if request.client else "unknown"
    _check_rate_limit(f"auth:{client_ip}", max_requests=20)

    # ── Validate JWT ──────────────────────────────────────────────────────
    validator = get_token_validator()
    try:
        claims = await validator.validate(credentials.credentials)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    identity = validator.extract_identity(claims)
    azure_oid: str = identity["azure_oid"]
    email: str = identity["email"]
    display_name: str = identity["display_name"]

    # ── Resolve tenant from header ────────────────────────────────────────
    tenant_slug = request.headers.get("X-Tenant-Slug", "")

    # ── Open admin session (no RLS) for user upsert + tenant resolution ──
    factory = get_session_factory()
    async with factory() as session:
        # Upsert user
        user = await upsert_user(session, azure_oid, email, display_name)

        if user.is_global_admin and not tenant_slug:
            # Global admins can operate without a tenant context
            # (e.g. /api/v1/auth/me, /api/v1/tenants listing)
            await session.commit()
            ctx = CurrentUser(
                user=user,
                tenant_ctx=None,  # type: ignore[arg-type]
                role_assignments=[],
                _permissions=set(Permission),
            )
            request.state.current_user = ctx
            structlog.contextvars.bind_contextvars(
                user_id=str(user.id),
                is_global_admin=True,
            )
            return ctx

        if not tenant_slug:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="X-Tenant-Slug header is required for this endpoint.",
            )

        # Check cached tenant on request state (set by TenantMiddleware if applicable)
        company, enterprise = await resolve_tenant(session, tenant_slug)

        # Fetch role assignments in this tenant
        role_assignments = await get_user_role_assignments(
            session, user.id, company.tenant_id
        )

        if not role_assignments and not user.is_global_admin:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"User has no role in tenant '{tenant_slug}'.",
            )

        await session.commit()

    tenant_ctx = TenantContext(company=company, enterprise=enterprise)
    permissions = CurrentUser.build_permissions(role_assignments, user.is_global_admin)

    ctx = CurrentUser(
        user=user,
        tenant_ctx=tenant_ctx,
        role_assignments=role_assignments,
        _permissions=permissions,
    )

    # Attach to request state for middleware logging
    request.state.current_user = ctx
    request.state.tenant_id = company.tenant_id

    structlog.contextvars.bind_contextvars(
        user_id=str(user.id),
        tenant_id=str(company.tenant_id),
        tenant_slug=tenant_slug,
    )

    return ctx


CurrentUserDep = Annotated[CurrentUser, Depends(get_current_user)]


# ---------------------------------------------------------------------------
# Tenant-scoped database session
# ---------------------------------------------------------------------------


async def get_tenant_db(
    current_user: CurrentUserDep,
) -> AsyncSession:
    """
    Yield an AsyncSession with Azure SQL SESSION_CONTEXT set to the user's tenant.

    This is the standard database dependency for all tenant-scoped endpoints.
    The RLS predicates on each table enforce isolation automatically.
    """
    if current_user.tenant_ctx is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tenant context is required for this operation.",
        )
    factory = get_session_factory()
    async with factory() as session:
        await set_tenant_context(session, current_user.tenant_id)
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


TenantDB = Annotated[AsyncSession, Depends(get_tenant_db)]


# ---------------------------------------------------------------------------
# Cosmos DB
# ---------------------------------------------------------------------------


def get_cosmos_dep(current_user: CurrentUserDep) -> ContainerProxy:
    """Return the Cosmos container scoped to the current user's tenant."""
    return get_tenant_container(current_user.tenant_id)


CosmosDep = Annotated[ContainerProxy, Depends(get_cosmos_dep)]


# ---------------------------------------------------------------------------
# RBAC dependency factories
# ---------------------------------------------------------------------------


def require_permission(*permissions: Permission):
    """
    FastAPI dependency factory that enforces one or more permissions (AND logic).

    Usage::

        @router.get("/scripts")
        async def list_scripts(
            _=Depends(require_permission(Permission.SCRIPT_READ))
        ):
    """

    def _check(current_user: CurrentUserDep) -> CurrentUser:
        for perm in permissions:
            if not current_user.has_permission(perm):
                logger.warning(
                    "permission_denied",
                    user_id=str(current_user.user_id),
                    required_permission=perm.value,
                    user_roles=[r.value for r in current_user.roles_in_tenant()],
                )
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Permission denied: {perm.value}",
                )
        return current_user

    return _check


def require_any_permission(*permissions: Permission):
    """Dependency factory that enforces at least one permission (OR logic)."""

    def _check(current_user: CurrentUserDep) -> CurrentUser:
        if not current_user.has_any_permission(*permissions):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires one of: {[p.value for p in permissions]}",
            )
        return current_user

    return _check


def require_global_admin(current_user: CurrentUserDep) -> CurrentUser:
    """Dependency that allows only Global Admins."""
    if not current_user.is_global_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Global Administrator access required.",
        )
    return current_user


def require_roles(*roles: RoleCode):
    """
    Dependency factory that allows any of the listed roles (OR logic).

    Usage::

        @router.post("/users", dependencies=[Depends(require_roles(RoleCode.CADM))])
    """

    def _check(current_user: CurrentUserDep) -> CurrentUser:
        user_roles = set(current_user.roles_in_tenant())
        if not user_roles & set(roles):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires one of: {[r.value for r in roles]}",
            )
        return current_user

    return _check


GlobalAdminOnly = Annotated[CurrentUser, Depends(require_global_admin)]


# ---------------------------------------------------------------------------
# Domain scope helpers
# ---------------------------------------------------------------------------


def check_domain_scope(user: CurrentUser, business_domain: str | None) -> None:
    """
    Enforce BPO domain restrictions.

    BPO users can only access records in their assigned domain(s).
    All other roles pass through unchecked.
    """
    from app.models.user import RoleCode as RC
    if RC.BUSINESS_PROCESS_OWNER not in user.roles_in_tenant():
        return
    if business_domain is None:
        return
    allowed = set(user.domain_codes())
    if business_domain not in allowed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"BPO access denied: domain '{business_domain}' not in your assigned domains.",
        )


def can_access_tenant(user: CurrentUser, company_id: UUID) -> bool:
    """
    Return True if the user is authorised to access the given company.

    Global admins can access any company. Other users can only access their
    current tenant.
    """
    if user.is_global_admin:
        return True
    return user.tenant_ctx is not None and user.company_id == company_id


# ---------------------------------------------------------------------------
# Backward-compat shims used by old scaffolded routers
# ---------------------------------------------------------------------------

# Old code imported: from app.dependencies import CurrentUser (as annotation type)
# New CurrentUser is the dataclass from azure_ad. Re-export it here.
__all__ = [
    "CurrentUserDep",
    "TenantDB",
    "CosmosDep",
    "AdminSession",
    "SettingsDep",
    "GlobalAdminOnly",
    "require_permission",
    "require_any_permission",
    "require_global_admin",
    "require_roles",
    "check_domain_scope",
    "can_access_tenant",
    "CurrentUser",
]
