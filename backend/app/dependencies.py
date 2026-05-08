"""
FastAPI dependency injection wiring.

Provides reusable dependencies for:
- Authenticated current user (JWT → User)
- Tenant-scoped database session (sets SESSION_CONTEXT for RLS)
- Tenant-scoped Cosmos DB container
- RBAC permission checks
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

import structlog
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.azure_ad import TokenValidator, get_token_validator
from app.auth.permissions import Permission, RolePermissions
from app.config import Settings, get_settings
from app.cosmos import ContainerProxy, get_tenant_container
from app.database import get_session_factory, set_tenant_context
from app.models.user import User, UserRole

logger = structlog.get_logger(__name__)

_bearer_scheme = HTTPBearer(auto_error=True)


# ── Settings ─────────────────────────────────────────────────────────────────

def settings_dep() -> Settings:
    return get_settings()


SettingsDep = Annotated[Settings, Depends(settings_dep)]


# ── Authentication ────────────────────────────────────────────────────────────

async def get_current_user(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(_bearer_scheme)],
    validator: Annotated[TokenValidator, Depends(get_token_validator)],
    settings: SettingsDep,
) -> User:
    """
    Validate the Bearer JWT and return a User object populated from claims.
    The user is NOT loaded from the database here — claims are the source of truth
    for hot-path authentication. The User model is constructed from JWT claims.
    """
    try:
        claims = await validator.validate(credentials.credentials)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    tenant_id_str = claims.get("kaats_tenant_id")
    if not tenant_id_str:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token missing required kaats_tenant_id claim.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    roles_claim = claims.get("kaats_roles", [])
    role_str = roles_claim[0] if roles_claim else "VT"

    try:
        role = UserRole(role_str)
    except ValueError:
        role = UserRole.VALIDATION_TESTER

    user = User(
        id=UUID(claims["oid"]),
        tenant_id=UUID(tenant_id_str),
        entra_object_id=claims["oid"],
        email=claims.get("email", claims.get("preferred_username", "")),
        display_name=claims.get("name", ""),
        role=role,
        domains=claims.get("kaats_domains", []),
        is_active=True,
    )

    # Attach to request state for downstream middleware / logging
    request.state.user = user
    request.state.tenant_id = user.tenant_id
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


# ── Database ──────────────────────────────────────────────────────────────────

async def get_tenant_db(
    request: Request,
    current_user: CurrentUser,
) -> AsyncSession:
    """
    Yield a SQLAlchemy session with tenant RLS context pre-set.
    This is the standard DB dependency for all tenant-scoped endpoints.
    """
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


# ── Cosmos DB ─────────────────────────────────────────────────────────────────

async def get_cosmos_dep(current_user: CurrentUser) -> ContainerProxy:
    """Yield the Cosmos container scoped to the current user's tenant."""
    return get_tenant_container(current_user.tenant_id)


CosmosDep = Annotated[ContainerProxy, Depends(get_cosmos_dep)]


# ── RBAC ──────────────────────────────────────────────────────────────────────

class RequirePermission:
    """
    Callable dependency factory that enforces a single permission.

    Usage:
        @router.get("/projects", dependencies=[Depends(RequirePermission(Permission.PROJECT_READ))])
    """

    def __init__(self, permission: Permission) -> None:
        self.permission = permission

    def __call__(self, current_user: CurrentUser) -> User:
        allowed = RolePermissions.get(current_user.role, set())
        if self.permission not in allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{current_user.role.value}' does not have permission: {self.permission.value}",
            )
        return current_user


def require_roles(*roles: UserRole):
    """
    Callable dependency factory that enforces one of the listed roles.

    Usage:
        @router.post("/users", dependencies=[Depends(require_roles(UserRole.GADM, UserRole.EADM))])
    """

    def _check(current_user: CurrentUser) -> User:
        if current_user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"This endpoint requires one of: {[r.value for r in roles]}",
            )
        return current_user

    return _check


def require_global_admin(current_user: CurrentUser) -> User:
    if current_user.role != UserRole.GLOBAL_ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Global Administrator access required.",
        )
    return current_user


GlobalAdminOnly = Annotated[User, Depends(require_global_admin)]
