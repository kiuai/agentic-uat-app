"""
RBAC enforcement utilities.

The primary RBAC enforcement happens via FastAPI Depends() in individual
route handlers using RequirePermission and require_roles from dependencies.py.

This module provides additional helpers for service-layer permission checks
that go beyond what route-level dependencies can express — for example,
restricting a Validation Tester to only their assigned executions, or
restricting a BPO to their domain.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import HTTPException, status

from app.auth.permissions import Permission, has_permission
from app.models.user import User, UserRole


def assert_permission(user: User, permission: Permission) -> None:
    """Raise 403 if the user lacks the given permission."""
    if not has_permission(user.role, permission):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Permission denied: {permission.value}",
        )


def assert_domain_access(user: User, domain_code: str | None) -> None:
    """
    BPO users can only access records in their assigned domains.
    Other roles always pass this check.
    """
    if user.role != UserRole.BUSINESS_PROCESS_OWNER:
        return
    if domain_code is None:
        return
    if domain_code not in (user.domains or []):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"BPO access denied: domain '{domain_code}' not in your assigned domains.",
        )


def assert_assigned_execution(user: User, assigned_to_id: UUID) -> None:
    """
    Validation Testers can only act on executions assigned to them.
    Other roles always pass this check.
    """
    if user.role != UserRole.VALIDATION_TESTER:
        return
    if user.id != assigned_to_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Validation Testers can only execute scripts assigned to them.",
        )
