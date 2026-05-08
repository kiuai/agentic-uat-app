"""Unit tests for RBAC permission matrix."""

from __future__ import annotations

import pytest

from app.auth.permissions import Permission, has_permission, RolePermissions
from app.models.user import UserRole


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


def test_system_manager_can_manage_environments() -> None:
    assert has_permission(UserRole.SYSTEM_MANAGER, Permission.ENVIRONMENT_MANAGE)


def test_bpo_cannot_manage_environments() -> None:
    assert not has_permission(UserRole.BUSINESS_PROCESS_OWNER, Permission.ENVIRONMENT_MANAGE)


def test_all_roles_have_permissions_defined() -> None:
    for role in UserRole:
        assert role in RolePermissions, f"Role {role.value} has no permissions defined"
        assert len(RolePermissions[role]) > 0, f"Role {role.value} has empty permissions"
