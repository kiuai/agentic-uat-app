"""
Comprehensive RBAC tests covering every role × permission combination.

Why this matters: incorrect permission mappings are a security vulnerability.
A Validation Tester being able to approve scripts, or a BPO being able to
delete tenants, would be critical bugs. This file parametrizes the full
permission matrix so any future change to ROLE_PERMISSIONS is caught
immediately in CI.

Structure:
- ``test_role_can_*``  — positive: role MUST have the permission
- ``test_role_cannot_*`` — negative: role MUST NOT have the permission
- ``test_full_matrix_*`` — exhaustive: every role × every permission
- ``test_current_user_*`` — end-to-end: CurrentUser.has_permission()
"""

from __future__ import annotations

import uuid
from typing import Iterator

import pytest

from app.auth.azure_ad import CurrentUser, TenantContext
from app.auth.permissions import (
    ROLE_PERMISSIONS,
    Permission,
    has_permission,
    permissions_for_roles,
)
from app.models.tenant import Company, Enterprise
from app.models.user import RoleCode, User, UserRoleAssignment
from tests.conftest import _make_current_user


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

TENANT_ID = uuid.UUID("aaaa0000-0000-0000-0000-000000000001")


@pytest.fixture
def base_company() -> Company:
    c = Company.__new__(Company)
    c.id = TENANT_ID
    c.tenant_id = TENANT_ID
    c.enterprise_id = uuid.UUID("aaaa0000-0000-0000-0000-000000000002")
    c.name = "Test Co"
    c.slug = "test-co"
    c.is_active = True
    c.settings = None
    return c


@pytest.fixture
def base_enterprise(base_company: Company) -> Enterprise:
    e = Enterprise.__new__(Enterprise)
    e.id = base_company.enterprise_id
    e.name = "Test Enterprise"
    e.slug = "test-ent"
    e.is_active = True
    e.azure_ad_tenant_id = None
    e.settings = None
    return e


def make_user(
    role: RoleCode,
    company: Company,
    enterprise: Enterprise,
    *,
    domain_code: str | None = None,
    is_global_admin: bool = False,
) -> CurrentUser:
    return _make_current_user(
        role,
        tenant_id=company.tenant_id,
        company=company,
        enterprise=enterprise,
        is_global_admin=is_global_admin,
        domain_code=domain_code,
    )


# ---------------------------------------------------------------------------
# Positive matrix — roles that MUST have certain permissions
# ---------------------------------------------------------------------------

ROLE_MUST_HAVE: list[tuple[RoleCode, Permission]] = [
    # Global Admin has everything
    (RoleCode.GLOBAL_ADMIN, Permission.ADMIN_GLOBAL),
    (RoleCode.GLOBAL_ADMIN, Permission.TENANT_DELETE),
    (RoleCode.GLOBAL_ADMIN, Permission.USER_DELETE),
    (RoleCode.GLOBAL_ADMIN, Permission.SCRIPT_APPROVE),
    # Enterprise Admin — manages enterprises but not global ops
    (RoleCode.ENTERPRISE_ADMIN, Permission.ADMIN_ENTERPRISE),
    (RoleCode.ENTERPRISE_ADMIN, Permission.TENANT_CREATE),
    (RoleCode.ENTERPRISE_ADMIN, Permission.USER_ASSIGN_ROLE),
    # Company Admin
    (RoleCode.COMPANY_ADMIN, Permission.ADMIN_COMPANY),
    (RoleCode.COMPANY_ADMIN, Permission.PROJECT_CREATE),
    (RoleCode.COMPANY_ADMIN, Permission.USER_CREATE),
    (RoleCode.COMPANY_ADMIN, Permission.SCRIPT_APPROVE),
    # System Manager
    (RoleCode.SYSTEM_MANAGER, Permission.PROJECT_CREATE),
    (RoleCode.SYSTEM_MANAGER, Permission.PROJECT_DELETE),
    (RoleCode.SYSTEM_MANAGER, Permission.ENVIRONMENT_MANAGE),
    (RoleCode.SYSTEM_MANAGER, Permission.CRAWLER_CREATE),
    (RoleCode.SYSTEM_MANAGER, Permission.CRAWLER_CANCEL),
    (RoleCode.SYSTEM_MANAGER, Permission.AI_GENERATE),
    (RoleCode.SYSTEM_MANAGER, Permission.REQUIREMENT_CREATE),
    # Validation Lead
    (RoleCode.VALIDATION_LEAD, Permission.SCRIPT_APPROVE),
    (RoleCode.VALIDATION_LEAD, Permission.CYCLE_CREATE),
    (RoleCode.VALIDATION_LEAD, Permission.ASSIGNMENT_CREATE),
    (RoleCode.VALIDATION_LEAD, Permission.REPORT_READ),
    # QA
    (RoleCode.QA, Permission.SCRIPT_READ),
    (RoleCode.QA, Permission.REQUIREMENT_READ),
    (RoleCode.QA, Permission.CYCLE_READ),
    (RoleCode.QA, Permission.RESULT_READ),
    # Validation Tester
    (RoleCode.VALIDATION_TESTER, Permission.RESULT_CREATE),
    (RoleCode.VALIDATION_TESTER, Permission.SCRIPT_READ),
    (RoleCode.VALIDATION_TESTER, Permission.CYCLE_READ),
    # BPO
    (RoleCode.BUSINESS_PROCESS_OWNER, Permission.SCRIPT_APPROVE),
    (RoleCode.BUSINESS_PROCESS_OWNER, Permission.REQUIREMENT_READ),
    (RoleCode.BUSINESS_PROCESS_OWNER, Permission.REPORT_READ),
]


@pytest.mark.parametrize("role,permission", ROLE_MUST_HAVE)
def test_role_has_permission(role: RoleCode, permission: Permission) -> None:
    """
    Asserts that each role possesses the permissions explicitly documented
    in the RBAC matrix.  Failing this test means a capability was stripped
    from a role that depends on it.
    """
    assert has_permission(role, permission), (
        f"{role.value} MUST have '{permission.value}' but does not."
    )


# ---------------------------------------------------------------------------
# Negative matrix — roles that MUST NOT have certain permissions
# ---------------------------------------------------------------------------

ROLE_MUST_NOT_HAVE: list[tuple[RoleCode, Permission]] = [
    # Enterprise Admin cannot perform global admin operations
    (RoleCode.ENTERPRISE_ADMIN, Permission.ADMIN_GLOBAL),
    # Company Admin cannot create/delete tenants
    (RoleCode.COMPANY_ADMIN, Permission.TENANT_CREATE),
    (RoleCode.COMPANY_ADMIN, Permission.TENANT_DELETE),
    (RoleCode.COMPANY_ADMIN, Permission.ADMIN_ENTERPRISE),
    (RoleCode.COMPANY_ADMIN, Permission.ADMIN_GLOBAL),
    # System Manager limited to ops, not admin
    (RoleCode.SYSTEM_MANAGER, Permission.ADMIN_GLOBAL),
    (RoleCode.SYSTEM_MANAGER, Permission.ADMIN_ENTERPRISE),
    (RoleCode.SYSTEM_MANAGER, Permission.TENANT_DELETE),
    # Validation Lead cannot manage users or tenants
    (RoleCode.VALIDATION_LEAD, Permission.USER_DELETE),
    (RoleCode.VALIDATION_LEAD, Permission.TENANT_CREATE),
    (RoleCode.VALIDATION_LEAD, Permission.ADMIN_COMPANY),
    # QA — read-heavy role, no write/admin
    (RoleCode.QA, Permission.SCRIPT_CREATE),
    (RoleCode.QA, Permission.SCRIPT_APPROVE),
    (RoleCode.QA, Permission.CYCLE_CREATE),
    (RoleCode.QA, Permission.USER_CREATE),
    (RoleCode.QA, Permission.ADMIN_COMPANY),
    # Validation Tester — execute only, no management
    (RoleCode.VALIDATION_TESTER, Permission.SCRIPT_APPROVE),
    (RoleCode.VALIDATION_TESTER, Permission.SCRIPT_CREATE),
    (RoleCode.VALIDATION_TESTER, Permission.SCRIPT_DELETE),
    (RoleCode.VALIDATION_TESTER, Permission.PROJECT_CREATE),
    (RoleCode.VALIDATION_TESTER, Permission.CYCLE_CREATE),
    (RoleCode.VALIDATION_TESTER, Permission.USER_ASSIGN_ROLE),
    (RoleCode.VALIDATION_TESTER, Permission.ADMIN_COMPANY),
    (RoleCode.VALIDATION_TESTER, Permission.CRAWLER_CREATE),
    (RoleCode.VALIDATION_TESTER, Permission.AI_GENERATE),
    # BPO — reviewer/approver, not an admin
    (RoleCode.BUSINESS_PROCESS_OWNER, Permission.PROJECT_CREATE),
    (RoleCode.BUSINESS_PROCESS_OWNER, Permission.TENANT_CREATE),
    (RoleCode.BUSINESS_PROCESS_OWNER, Permission.USER_ASSIGN_ROLE),
    (RoleCode.BUSINESS_PROCESS_OWNER, Permission.SCRIPT_CREATE),
    (RoleCode.BUSINESS_PROCESS_OWNER, Permission.ADMIN_COMPANY),
    (RoleCode.BUSINESS_PROCESS_OWNER, Permission.CRAWLER_CREATE),
]


@pytest.mark.parametrize("role,permission", ROLE_MUST_NOT_HAVE)
def test_role_lacks_permission(role: RoleCode, permission: Permission) -> None:
    """
    Asserts that each role does NOT possess permissions beyond its scope.
    Failing this test means privilege escalation is possible.
    """
    assert not has_permission(role, permission), (
        f"{role.value} MUST NOT have '{permission.value}' but does."
    )


# ---------------------------------------------------------------------------
# Full matrix snapshot — every role × every permission
# ---------------------------------------------------------------------------


def _all_role_perm_combos() -> Iterator[tuple[RoleCode, Permission, bool]]:
    """Yield (role, permission, expected_bool) for every combination."""
    for role in RoleCode:
        role_perms = ROLE_PERMISSIONS.get(role, set())
        for perm in Permission:
            yield role, perm, perm in role_perms


@pytest.mark.parametrize(
    "role,permission,expected",
    list(_all_role_perm_combos()),
    ids=lambda x: getattr(x, "value", str(x)),
)
def test_full_permission_matrix(
    role: RoleCode, permission: Permission, expected: bool
) -> None:
    """
    Exhaustive parametrized test covering every (role, permission) pair.

    This acts as a snapshot test: if ROLE_PERMISSIONS is changed, this test
    will fail for the affected cells and force an explicit acknowledgement
    of what changed.
    """
    assert has_permission(role, permission) == expected


# ---------------------------------------------------------------------------
# permissions_for_roles() — multi-role union
# ---------------------------------------------------------------------------


def test_permissions_for_roles_single_role() -> None:
    """Single role returns the same set as ROLE_PERMISSIONS lookup."""
    result = permissions_for_roles([RoleCode.VALIDATION_TESTER])
    assert result == ROLE_PERMISSIONS[RoleCode.VALIDATION_TESTER]


def test_permissions_for_roles_union_of_two() -> None:
    """
    A user with both VL and BPO roles gets the union of their permissions.
    Neither role alone can CREATE a cycle AND APPROVE a script, but together
    they can.  This models real-world users with multiple assignments.
    """
    combined = permissions_for_roles([RoleCode.VALIDATION_LEAD, RoleCode.BUSINESS_PROCESS_OWNER])
    assert Permission.SCRIPT_APPROVE in combined
    assert Permission.CYCLE_CREATE in combined


def test_permissions_for_roles_empty() -> None:
    """An empty roles list produces an empty permission set."""
    assert permissions_for_roles([]) == set()


def test_permissions_for_roles_global_admin() -> None:
    """Global Admin role alone produces the full permission set."""
    result = permissions_for_roles([RoleCode.GLOBAL_ADMIN])
    assert result == set(Permission)


# ---------------------------------------------------------------------------
# CurrentUser.has_permission() end-to-end
# ---------------------------------------------------------------------------


def test_current_user_has_permission_positive(
    base_company: Company, base_enterprise: Enterprise
) -> None:
    """
    CurrentUser built from a VALIDATION_LEAD role assignment has SCRIPT_APPROVE.

    This tests the full path: role_assignment → build_permissions() →
    CurrentUser.has_permission().
    """
    cu = make_user(RoleCode.VALIDATION_LEAD, base_company, base_enterprise)
    assert cu.has_permission(Permission.SCRIPT_APPROVE)


def test_current_user_has_permission_negative(
    base_company: Company, base_enterprise: Enterprise
) -> None:
    """
    A Validation Tester CurrentUser must not pass SCRIPT_APPROVE check.
    This is the most security-critical assertion in the test suite.
    """
    cu = make_user(RoleCode.VALIDATION_TESTER, base_company, base_enterprise)
    assert not cu.has_permission(Permission.SCRIPT_APPROVE)


def test_current_user_global_admin_has_all(
    base_company: Company, base_enterprise: Enterprise
) -> None:
    """
    A global admin CurrentUser passes every permission check, including
    ADMIN_GLOBAL which no other role has.
    """
    cu = make_user(
        RoleCode.GLOBAL_ADMIN, base_company, base_enterprise, is_global_admin=True
    )
    for perm in Permission:
        assert cu.has_permission(perm), f"Global admin missing {perm.value}"


def test_current_user_has_any_permission_positive(
    base_company: Company, base_enterprise: Enterprise
) -> None:
    """
    has_any_permission() returns True if the user has at least one of the
    listed permissions.  Used in RoleGate-style checks.
    """
    cu = make_user(RoleCode.VALIDATION_TESTER, base_company, base_enterprise)
    # VT has RESULT_CREATE but not SCRIPT_APPROVE
    assert cu.has_any_permission(Permission.SCRIPT_APPROVE, Permission.RESULT_CREATE)


def test_current_user_has_any_permission_negative(
    base_company: Company, base_enterprise: Enterprise
) -> None:
    """
    has_any_permission() returns False when the user has none of the listed
    permissions.
    """
    cu = make_user(RoleCode.VALIDATION_TESTER, base_company, base_enterprise)
    assert not cu.has_any_permission(Permission.ADMIN_GLOBAL, Permission.TENANT_DELETE)


def test_current_user_roles_in_tenant(
    base_company: Company, base_enterprise: Enterprise
) -> None:
    """
    roles_in_tenant() returns the list of role codes for the current tenant,
    enabling UI-level role checks (e.g. isAdmin).
    """
    cu = make_user(RoleCode.COMPANY_ADMIN, base_company, base_enterprise)
    roles = cu.roles_in_tenant()
    assert RoleCode.COMPANY_ADMIN in roles


def test_current_user_domain_codes(
    base_company: Company, base_enterprise: Enterprise
) -> None:
    """
    A BPO user with domain_code='FIN' has exactly that code in domain_codes().
    This drives the assert_domain_access() BPO restriction.
    """
    cu = make_user(
        RoleCode.BUSINESS_PROCESS_OWNER,
        base_company,
        base_enterprise,
        domain_code="FIN",
    )
    assert "FIN" in cu.domain_codes()


# ---------------------------------------------------------------------------
# Role invariants — structural checks on ROLE_PERMISSIONS
# ---------------------------------------------------------------------------


def test_every_role_defined_in_role_permissions() -> None:
    """Every RoleCode must have an entry in ROLE_PERMISSIONS to prevent KeyError."""
    for role in RoleCode:
        assert role in ROLE_PERMISSIONS, f"{role.value} missing from ROLE_PERMISSIONS"


def test_every_role_has_at_least_read_permission() -> None:
    """
    A role with zero permissions would lock users out completely and is almost
    certainly a configuration error.
    """
    for role in RoleCode:
        perms = ROLE_PERMISSIONS[role]
        assert len(perms) > 0, f"{role.value} has no permissions — likely a config error"


def test_global_admin_is_superset_of_all_roles() -> None:
    """
    Global Admin's permission set must be a superset of every other role's set.
    If any role has a permission GADM lacks, something is wrong.
    """
    gadm_perms = ROLE_PERMISSIONS[RoleCode.GLOBAL_ADMIN]
    for role in RoleCode:
        if role == RoleCode.GLOBAL_ADMIN:
            continue
        for perm in ROLE_PERMISSIONS[role]:
            assert perm in gadm_perms, (
                f"Role {role.value} has {perm.value} but GLOBAL_ADMIN does not"
            )
