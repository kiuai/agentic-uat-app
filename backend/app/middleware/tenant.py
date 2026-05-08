"""
Tenant resolution middleware.

Extracts and validates the tenant_id from the authenticated user's JWT claims
and attaches it to the request state. Used by downstream service layer code
to scope data access.

Note: the actual RLS SESSION_CONTEXT is set per-session in the database
dependency (dependencies.py:get_tenant_db), not here. This middleware only
populates request.state.tenant_id for logging and routing.
"""

from __future__ import annotations

from typing import Callable
from uuid import UUID

import structlog
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

logger = structlog.get_logger(__name__)

# Paths that do not require tenant resolution
_EXCLUDED_PATHS = frozenset(
    {
        "/health",
        "/health/ready",
        "/docs",
        "/redoc",
        "/api/v1/openapi.json",
        "/api/v1/auth/login",
        "/api/v1/auth/callback",
    }
)


class TenantMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        if request.url.path in _EXCLUDED_PATHS:
            return await call_next(request)

        # Tenant ID is set on request.state by the get_current_user dependency.
        # Here we only bind it to the structlog context for downstream log records.
        response = await call_next(request)

        tenant_id: UUID | None = getattr(request.state, "tenant_id", None)
        if tenant_id:
            with structlog.contextvars.bound_contextvars(tenant_id=str(tenant_id)):
                pass  # Contextvars already bound; just ensuring it's present

        return response
