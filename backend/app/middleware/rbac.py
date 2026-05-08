"""
RBAC audit middleware and permission enforcement helpers.

Responsibilities
----------------
1. Log all permission checks to structlog with user_id, resource, permission.
2. Write audit events to the audit_logs SQL table for sensitive operations
   (SCRIPT_APPROVE, SCRIPT_DELETE, USER_ASSIGN_ROLE, ADMIN_* etc.).
3. Throttle failed authentication attempts per IP (in-memory).

The primary per-endpoint permission enforcement is done via
require_permission() in dependencies.py. This module provides:
  - assert_permission()        — service-layer guard (raises 403)
  - assert_domain_access()     — BPO domain guard
  - assert_assigned_execution()— VT assignment guard
  - write_audit_event()        — async audit record writer
  - FailedAuthThrottle         — tracks repeated auth failures
"""

from __future__ import annotations

import time
from collections import defaultdict
from uuid import UUID

import structlog
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.permissions import AUDIT_REQUIRED_PERMISSIONS, Permission
from app.models.audit_log import AuditLog
from app.models.user import RoleCode

logger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Permission assertion helpers (service layer)
# ---------------------------------------------------------------------------


def assert_permission(
    permissions: set[Permission],
    required: Permission,
    *,
    user_id: UUID | None = None,
) -> None:
    """
    Raise HTTP 403 if `required` is not in the caller's permission set.

    Use this inside service functions where you have the resolved permission
    set but not the full CurrentUser context.
    """
    if required not in permissions:
        logger.warning(
            "permission_denied",
            required=required.value,
            user_id=str(user_id) if user_id else None,
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Permission denied: {required.value}",
        )


def assert_domain_access(
    roles: list[RoleCode],
    domain_codes: list[str],
    target_domain: str | None,
) -> None:
    """
    Enforce BPO domain restrictions.

    If the user holds only the BPO role and target_domain is set, the domain
    must be in their assigned domain_codes. All other roles pass through.
    """
    non_bpo = [r for r in roles if r != RoleCode.BUSINESS_PROCESS_OWNER]
    if non_bpo:
        return  # Non-BPO roles are not domain-restricted
    if not roles:
        return
    if target_domain is None:
        return
    if target_domain not in domain_codes:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                f"BPO access denied: domain '{target_domain}' "
                "is not in your assigned domains."
            ),
        )


def assert_assigned_execution(
    roles: list[RoleCode],
    requester_id: UUID,
    assigned_to_id: UUID,
) -> None:
    """
    Validation Testers can only act on executions assigned to them.
    Other roles pass through.
    """
    vt_only = all(r == RoleCode.VALIDATION_TESTER for r in roles) and bool(roles)
    if not vt_only:
        return
    if requester_id != assigned_to_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Validation Testers can only execute scripts assigned to them.",
        )


# ---------------------------------------------------------------------------
# Audit logging
# ---------------------------------------------------------------------------


async def write_audit_event(
    session: AsyncSession,
    *,
    user_id: UUID,
    tenant_id: UUID,
    action: str,
    resource_type: str,
    resource_id: str,
    before_state: str | None = None,
    after_state: str | None = None,
    ip_address: str | None = None,
    permission: Permission | None = None,
) -> None:
    """
    Persist an audit record to the audit_logs table.

    Called automatically for any action involving an AUDIT_REQUIRED_PERMISSIONS
    permission. Can also be called directly from service functions for
    domain-specific audit trails (e.g. BPO approval).
    """
    log = AuditLog(
        user_id=user_id,
        tenant_id=tenant_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        before_state=before_state,
        after_state=after_state,
        ip_address=ip_address,
    )
    session.add(log)
    # Flush without committing — caller controls the transaction
    await session.flush()

    structlog.contextvars.bind_contextvars(audit_resource=f"{resource_type}/{resource_id}")
    logger.info(
        "audit_event",
        user_id=str(user_id),
        tenant_id=str(tenant_id),
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        permission=permission.value if permission else None,
    )


def is_auditable(permission: Permission) -> bool:
    """Return True if this permission requires an audit log entry."""
    return permission in AUDIT_REQUIRED_PERMISSIONS


# ---------------------------------------------------------------------------
# Failed auth throttle
# ---------------------------------------------------------------------------


class FailedAuthThrottle:
    """
    In-memory tracker for repeated authentication failures per IP.

    Blocks IPs that exceed `max_failures` within `window_seconds`.
    Not persistent — resets on process restart. Use Redis for multi-instance.
    """

    def __init__(self, max_failures: int = 10, window_seconds: int = 300) -> None:
        self._max = max_failures
        self._window = window_seconds
        # {ip: [timestamp, ...]}
        self._failures: dict[str, list[float]] = defaultdict(list)

    def record_failure(self, ip: str) -> None:
        now = time.monotonic()
        self._failures[ip] = [
            ts for ts in self._failures[ip] if now - ts < self._window
        ]
        self._failures[ip].append(now)

    def is_blocked(self, ip: str) -> bool:
        now = time.monotonic()
        recent = [ts for ts in self._failures.get(ip, []) if now - ts < self._window]
        return len(recent) >= self._max

    def clear(self, ip: str) -> None:
        self._failures.pop(ip, None)


# Module-level singleton
auth_throttle = FailedAuthThrottle()
