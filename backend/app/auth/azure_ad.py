"""
Azure Entra ID (formerly Azure AD) JWT validation and user provisioning.

Flow
----
1. Bearer token arrives in Authorization header.
2. AzureADTokenValidator fetches JWKS from Entra ID, caches with TTL.
3. JWT is validated: signature (RS256), expiry, audience, issuer.
4. Claims are extracted: oid, email, name, roles, groups.
5. User is upserted in Azure SQL on first login and on profile changes.
6. A CurrentUser context object is returned with the resolved tenant, all
   role assignments, and the union permission set.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

import httpx
import structlog
from fastapi import HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.permissions import ROLE_PERMISSIONS, Permission, RoleCode
from app.config import Settings, get_settings
from app.models.tenant import Company, Enterprise
from app.models.user import User, UserRoleAssignment

logger = structlog.get_logger(__name__)

_JWKS_TTL_SECONDS = 3600
_bearer_scheme = HTTPBearer(auto_error=True)


# ---------------------------------------------------------------------------
# CurrentUser context object
# ---------------------------------------------------------------------------


@dataclass
class TenantContext:
    """Resolved tenant details attached to every authenticated request."""

    company: Company
    enterprise: Enterprise

    @property
    def company_id(self) -> UUID:
        return self.company.id

    @property
    def tenant_id(self) -> UUID:
        return self.company.tenant_id

    @property
    def enterprise_id(self) -> UUID:
        return self.enterprise.id


@dataclass
class CurrentUser:
    """
    Fully resolved authentication context for a single request.

    Built by get_current_user() after JWT validation + DB upsert + tenant
    resolution. Passed as a FastAPI Depends() result to all route handlers.
    """

    user: User
    tenant_ctx: TenantContext
    role_assignments: list[UserRoleAssignment] = field(default_factory=list)
    _permissions: set[Permission] = field(default_factory=set)

    # ── Convenience properties ─────────────────────────────────────────────

    @property
    def user_id(self) -> UUID:
        return self.user.id

    @property
    def tenant_id(self) -> UUID:
        return self.tenant_ctx.tenant_id

    @property
    def company_id(self) -> UUID:
        return self.tenant_ctx.company_id

    @property
    def enterprise_id(self) -> UUID:
        return self.tenant_ctx.enterprise_id

    @property
    def is_global_admin(self) -> bool:
        return self.user.is_global_admin

    @property
    def email(self) -> str:
        return self.user.email

    @property
    def display_name(self) -> str:
        return self.user.display_name

    # ── Permission helpers ─────────────────────────────────────────────────

    def has_permission(self, permission: Permission) -> bool:
        return permission in self._permissions

    def has_any_permission(self, *permissions: Permission) -> bool:
        return bool(self._permissions & set(permissions))

    def roles_in_tenant(self) -> list[RoleCode]:
        return [RoleCode(r.role) for r in self.role_assignments]

    def domain_codes(self) -> list[str]:
        """Return all domain codes from BPO role assignments."""
        return [
            r.domain_code
            for r in self.role_assignments
            if r.domain_code is not None
        ]

    @classmethod
    def build_permissions(
        cls, role_assignments: list[UserRoleAssignment], is_global_admin: bool
    ) -> set[Permission]:
        """Union of all permissions from all role assignments in the tenant."""
        if is_global_admin:
            return set(Permission)
        perms: set[Permission] = set()
        for ra in role_assignments:
            try:
                role = RoleCode(ra.role)
                perms |= ROLE_PERMISSIONS.get(role, set())
            except ValueError:
                pass
        return perms


# ---------------------------------------------------------------------------
# JWKS cache
# ---------------------------------------------------------------------------


class _JwksCache:
    def __init__(self, ttl: int = _JWKS_TTL_SECONDS) -> None:
        self._ttl = ttl
        self._keys: dict[str, Any] = {}
        self._fetched_at: float = 0.0
        self._lock = asyncio.Lock()

    def _is_stale(self, kid: str) -> bool:
        return (
            time.monotonic() - self._fetched_at > self._ttl
            or kid not in self._keys
        )

    async def get_key(self, kid: str, jwks_uri: str) -> Any:
        if self._is_stale(kid):
            async with self._lock:
                # Double-check after acquiring lock
                if self._is_stale(kid):
                    await self._refresh(jwks_uri)

        key = self._keys.get(kid)
        if key is None:
            raise ValueError(f"No signing key found for kid={kid!r}. Known kids: {list(self._keys)}")
        return key

    async def _refresh(self, jwks_uri: str) -> None:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(jwks_uri)
            resp.raise_for_status()
            data = resp.json()

        self._keys = {k["kid"]: k for k in data.get("keys", [])}
        self._fetched_at = time.monotonic()
        logger.debug("jwks_refreshed", key_count=len(self._keys))


# Module-level singleton cache
_jwks_cache = _JwksCache()


# ---------------------------------------------------------------------------
# Token validator
# ---------------------------------------------------------------------------


class AzureADTokenValidator:
    """
    Validates Azure Entra ID RS256 JWTs and extracts standardised claims.

    Raises ValueError with a user-safe message on any validation failure.
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def validate(self, token: str) -> dict[str, Any]:
        """Validate token and return decoded claims dict."""
        try:
            header = jwt.get_unverified_header(token)
        except JWTError as exc:
            raise ValueError("Malformed token header.") from exc

        kid = header.get("kid")
        if not kid:
            raise ValueError("Token header missing 'kid' claim.")

        signing_key = await _jwks_cache.get_key(kid, self._settings.entra_jwks_uri)

        try:
            claims: dict[str, Any] = jwt.decode(
                token,
                signing_key,
                algorithms=["RS256"],
                audience=self._settings.azure_client_id,
                issuer=self._settings.entra_issuer,
                options={"verify_exp": True},
            )
        except JWTError as exc:
            logger.warning("token_validation_failed", error=str(exc))
            raise ValueError(f"Token validation failed: {exc}") from exc

        return claims

    def extract_identity(self, claims: dict[str, Any]) -> dict[str, Any]:
        """Extract normalised identity fields from raw JWT claims."""
        return {
            "azure_oid": claims["oid"],
            "email": claims.get("email") or claims.get("preferred_username", ""),
            "display_name": claims.get("name", ""),
            # App roles assigned in Azure AD app registration
            "app_roles": claims.get("roles", []),
            # Group membership (if group claims enabled in token config)
            "groups": claims.get("groups", []),
        }


# Backward-compat alias used by tests scaffolded against the old name
TokenValidator = AzureADTokenValidator


def get_token_validator() -> AzureADTokenValidator:
    return AzureADTokenValidator(get_settings())


# ---------------------------------------------------------------------------
# User upsert
# ---------------------------------------------------------------------------


async def upsert_user(
    session: AsyncSession,
    azure_oid: str,
    email: str,
    display_name: str,
) -> User:
    """
    Idempotently create or update a User row from Entra ID claims.

    Called on every authenticated request so that display_name/email changes
    in Azure AD propagate to KAATS automatically.
    """
    result = await session.execute(
        select(User).where(User.azure_oid == azure_oid)
    )
    user: User | None = result.scalar_one_or_none()

    if user is None:
        user = User(
            azure_oid=azure_oid,
            email=email,
            display_name=display_name,
            is_active=True,
            is_global_admin=False,
        )
        session.add(user)
        logger.info("user_provisioned", azure_oid=azure_oid, email=email)
    else:
        changed = False
        if user.email != email:
            user.email = email
            changed = True
        if user.display_name != display_name:
            user.display_name = display_name
            changed = True
        if changed:
            logger.debug("user_profile_updated", user_id=str(user.id))

    await session.flush()
    await session.refresh(user)
    return user


# ---------------------------------------------------------------------------
# Tenant resolution
# ---------------------------------------------------------------------------


async def resolve_tenant(
    session: AsyncSession,
    slug: str,
) -> tuple[Company, Enterprise]:
    """
    Resolve X-Tenant-Slug to (Company, Enterprise).

    Raises HTTPException(404) if slug is unknown.
    """
    result = await session.execute(
        select(Company).where(Company.slug == slug, Company.is_active.is_(True))
    )
    company: Company | None = result.scalar_one_or_none()
    if company is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tenant '{slug}' not found.",
        )

    ent_result = await session.execute(
        select(Enterprise).where(Enterprise.id == company.enterprise_id)
    )
    enterprise: Enterprise | None = ent_result.scalar_one_or_none()
    if enterprise is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Tenant data inconsistency: enterprise not found.",
        )

    return company, enterprise


async def get_user_role_assignments(
    session: AsyncSession,
    user_id: UUID,
    tenant_id: UUID,
) -> list[UserRoleAssignment]:
    """Fetch all role assignments for a user within a specific tenant."""
    result = await session.execute(
        select(UserRoleAssignment).where(
            UserRoleAssignment.user_id == user_id,
            UserRoleAssignment.tenant_id == tenant_id,
        )
    )
    return list(result.scalars().all())
