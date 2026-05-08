"""
Tenant resolution middleware.

Reads X-Tenant-Slug from request headers, resolves the Company and Enterprise
records, and attaches them to request.state so downstream dependencies do not
need to perform another DB round-trip.

Caches successful tenant lookups in a module-level LRU dict (TTL: 5 minutes)
to avoid a DB hit on every request for the same tenant.

The full permission check (does THIS user have access to THIS tenant?) is
performed in get_current_user(), not here, because we need the validated JWT
to identify the user.
"""

from __future__ import annotations

import time
from typing import Callable

import structlog
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

logger = structlog.get_logger(__name__)

# Paths exempt from tenant resolution
_EXCLUDED_PATHS = frozenset({
    "/health",
    "/health/ready",
    "/docs",
    "/redoc",
    "/api/v1/openapi.json",
    "/api/v1/auth/token",
    "/api/v1/auth/logout",
    "/metrics",
})

# Prefix patterns that are also excluded
_EXCLUDED_PREFIXES = ("/docs/", "/redoc/")

# Simple TTL cache: slug → (company_id, enterprise_id, fetched_at)
_TENANT_CACHE: dict[str, tuple[str, str, float]] = {}
_CACHE_TTL = 300.0  # 5 minutes


def _cache_get(slug: str) -> tuple[str, str] | None:
    entry = _TENANT_CACHE.get(slug)
    if entry is None:
        return None
    company_id, enterprise_id, fetched_at = entry
    if time.monotonic() - fetched_at > _CACHE_TTL:
        del _TENANT_CACHE[slug]
        return None
    return company_id, enterprise_id


def _cache_set(slug: str, company_id: str, enterprise_id: str) -> None:
    _TENANT_CACHE[slug] = (company_id, enterprise_id, time.monotonic())


def invalidate_tenant_cache(slug: str | None = None) -> None:
    """
    Evict one or all entries from the tenant cache.

    Call after Company.slug is changed or a Company is deactivated.
    """
    if slug is None:
        _TENANT_CACHE.clear()
    else:
        _TENANT_CACHE.pop(slug, None)


class TenantMiddleware(BaseHTTPMiddleware):
    """
    Attaches resolved tenant metadata to request.state before the route handler.

    Sets:
      request.state.tenant_slug    — raw header value (may be empty string)
      request.state.tenant_cached  — True if the slug was resolved from cache
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        path = request.url.path

        # Skip excluded paths
        if path in _EXCLUDED_PATHS or any(path.startswith(p) for p in _EXCLUDED_PREFIXES):
            return await call_next(request)

        slug = request.headers.get("X-Tenant-Slug", "").strip().lower()
        request.state.tenant_slug = slug
        request.state.tenant_cached = False

        if slug:
            cached = _cache_get(slug)
            if cached:
                company_id_str, enterprise_id_str = cached
                request.state.cached_company_id = company_id_str
                request.state.cached_enterprise_id = enterprise_id_str
                request.state.tenant_cached = True
                structlog.contextvars.bind_contextvars(tenant_slug=slug)

        response = await call_next(request)
        return response
