"""Unit tests for RBAC permission matrix."""

from __future__ import annotations

import pytest

from app.auth.permissions import (
    ROLE_PERMISSIONS,
    Permission,
    has_permission,
    permissions_for_roles,
)
from app.models.user import RoleCode

# Alias so tests read naturally
UserRole = RoleCode


def test_global_admin_has_all_permissions() -> None:
    for permission in Permission:
        assert has_permission(UserRole.GLOBAL_ADMIN, permission), (
            f"Global Admin should have permission {permission.value}"
        )


def test_validation_tester_cannot_approve_scripts() -> None:
    assert not has_permission(UserRole.VALIDATION_TESTER, Permission.SCRIPT_APPROVE)


def test_bpo_can_approve_scripts() -> None:
    assert has_permission(UserRole.BUSINESS_PROCESS_OWNER, Permission.SCRIPT_APPROVE)


def test_qa_cannot_create_scripts() -> None:
    assert not has_permission(UserRole.QA, Permission.SCRIPT_CREATE)


def test_validation_lead_can_approve_scripts() -> None:
    assert has_permission(UserRole.VALIDATION_LEAD, Permission.SCRIPT_APPROVE)


def test_system_manager_can_manage_projects() -> None:
    assert has_permission(UserRole.SYSTEM_MANAGER, Permission.PROJECT_CREATE)
    assert has_permission(UserRole.SYSTEM_MANAGER, Permission.PROJECT_DELETE)


def test_bpo_cannot_create_projects() -> None:
    assert not has_permission(UserRole.BUSINESS_PROCESS_OWNER, Permission.PROJECT_CREATE)


def test_all_roles_have_permissions_defined() -> None:
    for role in UserRole:
        assert role in ROLE_PERMISSIONS, f"Role {role.value} has no permissions defined"
        assert len(ROLE_PERMISSIONS[role]) > 0, f"Role {role.value} has empty permissions"


def test_enterprise_admin_lacks_admin_global() -> None:
    assert not has_permission(UserRole.ENTERPRISE_ADMIN, Permission.ADMIN_GLOBAL)


def test_company_admin_lacks_tenant_delete() -> None:
    assert not has_permission(UserRole.COMPANY_ADMIN, Permission.TENANT_DELETE)


def test_permissions_for_roles_union() -> None:
    """Multi-role union should include permissions from all roles."""
    combined = permissions_for_roles(
        [UserRole.VALIDATION_LEAD, UserRole.BUSINESS_PROCESS_OWNER]
    )
    assert Permission.SCRIPT_APPROVE in combined
    assert Permission.CYCLE_CREATE in combined
    assert Permission.REPORT_EXPORT in combined


def test_vt_cannot_delete_scripts() -> None:
    assert not has_permission(UserRole.VALIDATION_TESTER, Permission.SCRIPT_DELETE)


def test_system_manager_can_use_crawler() -> None:
    assert has_permission(UserRole.SYSTEM_MANAGER, Permission.CRAWLER_CREATE)
    assert has_permission(UserRole.SYSTEM_MANAGER, Permission.CRAWLER_CANCEL)


def test_vt_cannot_delete_tenant() -> None:
    assert not has_permission(UserRole.VALIDATION_TESTER, Permission.TENANT_DELETE)
