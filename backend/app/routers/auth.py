"""
Auth router — token exchange, user profile, logout, and tenant listing.

Endpoints
---------
POST /api/v1/auth/token    Exchange Azure AD auth code for KAATS session info
GET  /api/v1/auth/me       Return current user profile and role assignments
POST /api/v1/auth/logout   Invalidate/expire the current session
GET  /api/v1/auth/tenants  List all tenants the current user has access to
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.azure_ad import (
    AzureADTokenValidator,
    CurrentUser,
    get_token_validator,
    get_user_role_assignments,
    upsert_user,
)
from app.auth.permissions import Permission
from app.config import get_settings
from app.database import get_session_factory
from app.dependencies import (
    AdminSession,
    CurrentUserDep,
    SettingsDep,
    require_permission,
)
from app.middleware.rbac import auth_throttle
from app.models.tenant import Company, Enterprise
from app.models.user import User, UserRoleAssignment

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/auth", tags=["Auth"])
_bearer = HTTPBearer(auto_error=False)


# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------


class TokenExchangeRequest(BaseModel):
    """Azure AD authorization code + PKCE verifier for SPA token exchange."""
    code: str
    redirect_uri: str
    code_verifier: str | None = None
    tenant_slug: str | None = None


class RoleAssignmentOut(BaseModel):
    role: str
    tenant_id: uuid.UUID
    domain_code: str | None

    model_config = {"from_attributes": True}


class UserProfileOut(BaseModel):
    id: uuid.UUID
    azure_oid: str
    email: str
    display_name: str
    is_active: bool
    is_global_admin: bool
    roles: list[RoleAssignmentOut]
    last_login_at: datetime | None
    permissions: list[str]


class TenantOut(BaseModel):
    company_id: uuid.UUID
    tenant_id: uuid.UUID
    company_name: str
    company_slug: str
    enterprise_id: uuid.UUID
    enterprise_name: str
    roles: list[str]


class TokenResponse(BaseModel):
    user: UserProfileOut
    tenants: list[TenantOut]


class LogoutResponse(BaseModel):
    message: str


# ---------------------------------------------------------------------------
# POST /auth/token
# ---------------------------------------------------------------------------


@router.post(
    "/token",
    response_model=TokenResponse,
    summary="Exchange Azure AD auth code for KAATS session",
    status_code=status.HTTP_200_OK,
)
async def exchange_token(
    body: TokenExchangeRequest,
    request: Request,
    settings: SettingsDep,
) -> TokenResponse:
    """
    Validate an Azure AD authorization code (PKCE flow) and return:
    - The resolved user profile with role assignments.
    - All tenants the user has access to.

    The frontend calls this after the MSAL redirect completes. KAATS does
    not issue its own tokens — the Azure AD access token is used directly
    as the Bearer token for all subsequent API calls.

    For the SPA flow, MSAL acquires the token client-side. This endpoint
    primarily handles the ``/token`` call that follows the redirect to
    resolve the KAATS user + tenant list without requiring an X-Tenant-Slug.
    """
    client_ip = request.client.host if request.client else "unknown"

    # Check throttle before any processing
    if auth_throttle.is_blocked(client_ip):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many failed authentication attempts. Please try again later.",
            headers={"Retry-After": "300"},
        )

    # Exchange code for tokens via MSAL on-behalf-of
    # In a pure SPA + PKCE flow, the frontend already holds the access token.
    # We use this endpoint to introspect and provision the user server-side.
    try:
        import msal

        msal_app = msal.ConfidentialClientApplication(
            client_id=settings.azure_client_id,
            client_credential=settings.azure_client_secret,
            authority=f"https://login.microsoftonline.com/{settings.azure_tenant_id}",
        )
        result: dict[str, Any] = msal_app.acquire_token_by_authorization_code(
            code=body.code,
            scopes=[f"api://{settings.azure_client_id}/.default"],
            redirect_uri=body.redirect_uri,
        )
    except ImportError:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="MSAL not installed. Install 'msal' package.",
        )

    if "error" in result:
        auth_throttle.record_failure(client_ip)
        logger.warning(
            "token_exchange_failed",
            error=result.get("error"),
            description=result.get("error_description", ""),
            ip=client_ip,
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=result.get("error_description", "Token exchange failed."),
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Validate the returned access token
    validator = get_token_validator()
    try:
        claims = await validator.validate(result["access_token"])
    except ValueError as exc:
        auth_throttle.record_failure(client_ip)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    identity = validator.extract_identity(claims)
    auth_throttle.clear(client_ip)

    factory = get_session_factory()
    async with factory() as session:
        user = await upsert_user(
            session,
            azure_oid=identity["azure_oid"],
            email=identity["email"],
            display_name=identity["display_name"],
        )

        # Update last_login_at
        user.last_login_at = datetime.now(timezone.utc)

        # Fetch all tenants this user has roles in
        roles_result = await session.execute(
            select(UserRoleAssignment).where(
                UserRoleAssignment.user_id == user.id
            )
        )
        all_assignments: list[UserRoleAssignment] = list(roles_result.scalars().all())

        # Gather unique tenant_ids
        tenant_ids = list({ra.tenant_id for ra in all_assignments})

        tenants_out: list[TenantOut] = []
        for tenant_id in tenant_ids:
            comp_result = await session.execute(
                select(Company).where(Company.tenant_id == tenant_id)
            )
            company: Company | None = comp_result.scalar_one_or_none()
            if company is None or not company.is_active:
                continue

            ent_result = await session.execute(
                select(Enterprise).where(Enterprise.id == company.enterprise_id)
            )
            enterprise: Enterprise | None = ent_result.scalar_one_or_none()
            if enterprise is None:
                continue

            tenant_roles = [
                ra.role for ra in all_assignments if ra.tenant_id == tenant_id
            ]
            tenants_out.append(
                TenantOut(
                    company_id=company.id,
                    tenant_id=company.tenant_id,
                    company_name=company.name,
                    company_slug=company.slug,
                    enterprise_id=enterprise.id,
                    enterprise_name=enterprise.name,
                    roles=tenant_roles,
                )
            )

        await session.commit()

    role_assignments_out = [
        RoleAssignmentOut(
            role=ra.role,
            tenant_id=ra.tenant_id,
            domain_code=ra.domain_code,
        )
        for ra in all_assignments
    ]

    user_out = UserProfileOut(
        id=user.id,
        azure_oid=user.azure_oid,
        email=user.email,
        display_name=user.display_name,
        is_active=user.is_active,
        is_global_admin=user.is_global_admin,
        roles=role_assignments_out,
        last_login_at=user.last_login_at,
        permissions=[],  # Full permission list only available in tenant context
    )

    logger.info(
        "user_logged_in",
        user_id=str(user.id),
        email=user.email,
        tenant_count=len(tenants_out),
    )

    return TokenResponse(user=user_out, tenants=tenants_out)


# ---------------------------------------------------------------------------
# GET /auth/me
# ---------------------------------------------------------------------------


@router.get(
    "/me",
    response_model=UserProfileOut,
    summary="Get current authenticated user profile",
)
async def get_me(current_user: CurrentUserDep) -> UserProfileOut:
    """
    Return the authenticated user's profile, role assignments in the current
    tenant, and the resolved permission list.
    """
    role_assignments_out = [
        RoleAssignmentOut(
            role=ra.role,
            tenant_id=ra.tenant_id,
            domain_code=ra.domain_code,
        )
        for ra in current_user.role_assignments
    ]

    return UserProfileOut(
        id=current_user.user_id,
        azure_oid=current_user.user.azure_oid,
        email=current_user.email,
        display_name=current_user.display_name,
        is_active=current_user.user.is_active,
        is_global_admin=current_user.is_global_admin,
        roles=role_assignments_out,
        last_login_at=current_user.user.last_login_at,
        permissions=[p.value for p in current_user._permissions],
    )


# ---------------------------------------------------------------------------
# POST /auth/logout
# ---------------------------------------------------------------------------


@router.post(
    "/logout",
    response_model=LogoutResponse,
    summary="Invalidate current session",
)
async def logout(current_user: CurrentUserDep, request: Request) -> LogoutResponse:
    """
    Signal a client-side logout.

    KAATS uses Azure AD tokens — there is no server-side session to invalidate.
    This endpoint clears any rate-limit counters for the user's IP and logs
    the logout event for audit purposes.

    The client should discard the access token and call
    ``msalInstance.logoutRedirect()`` to revoke the Entra ID session.
    """
    client_ip = request.client.host if request.client else "unknown"
    auth_throttle.clear(client_ip)

    logger.info(
        "user_logged_out",
        user_id=str(current_user.user_id),
        email=current_user.email,
    )

    return LogoutResponse(message="Logged out successfully.")


# ---------------------------------------------------------------------------
# GET /auth/tenants
# ---------------------------------------------------------------------------


@router.get(
    "/tenants",
    response_model=list[TenantOut],
    summary="List tenants the current user has access to",
)
async def list_my_tenants(current_user: CurrentUserDep) -> list[TenantOut]:
    """
    Return all company tenants the authenticated user holds a role in.

    Global admins see all active tenants.
    """
    factory = get_session_factory()
    async with factory() as session:
        if current_user.is_global_admin:
            comp_result = await session.execute(
                select(Company).where(Company.is_active.is_(True))
            )
            companies: list[Company] = list(comp_result.scalars().all())
        else:
            # Fetch all role assignments for this user
            ra_result = await session.execute(
                select(UserRoleAssignment).where(
                    UserRoleAssignment.user_id == current_user.user_id
                )
            )
            all_ra: list[UserRoleAssignment] = list(ra_result.scalars().all())
            tenant_ids = list({ra.tenant_id for ra in all_ra})

            if not tenant_ids:
                return []

            comp_result = await session.execute(
                select(Company).where(
                    Company.tenant_id.in_(tenant_ids),
                    Company.is_active.is_(True),
                )
            )
            companies = list(comp_result.scalars().all())
            all_ra_by_tenant = {
                ra.tenant_id: [
                    x for x in all_ra if x.tenant_id == ra.tenant_id
                ]
                for ra in all_ra
            }

        tenants_out: list[TenantOut] = []
        for company in companies:
            ent_result = await session.execute(
                select(Enterprise).where(Enterprise.id == company.enterprise_id)
            )
            enterprise: Enterprise | None = ent_result.scalar_one_or_none()
            if enterprise is None:
                continue

            if current_user.is_global_admin:
                roles: list[str] = ["GADM"]
            else:
                tenant_ra = all_ra_by_tenant.get(company.tenant_id, [])
                roles = [ra.role for ra in tenant_ra]

            tenants_out.append(
                TenantOut(
                    company_id=company.id,
                    tenant_id=company.tenant_id,
                    company_name=company.name,
                    company_slug=company.slug,
                    enterprise_id=enterprise.id,
                    enterprise_name=enterprise.name,
                    roles=roles,
                )
            )

    return tenants_out
