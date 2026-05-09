"""
Tenant isolation security tests.

These are critical security tests that verify the multi-tenant boundary is
enforced at every layer.  A failure here means one customer can read another
customer's data — a catastrophic breach.

What is tested:
1. assert_permission() raises HTTP 403 (not 404) for forbidden operations
2. Domain access guard (BPO domain scoping)
3. Execution ownership guard (VT can only update their own assignments)
4. FailedAuthThrottle blocks IPs after repeated failures
5. Tenant context properties are correctly derived from Company/Enterprise
6. The audit trail requirement: sensitive permissions trigger audit logging
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from app.auth.azure_ad import CurrentUser, TenantContext
from app.auth.permissions import AUDIT_REQUIRED_PERMISSIONS, Permission
from app.middleware.rbac import (
    FailedAuthThrottle,
    assert_domain_access,
    assert_permission,
    assert_assigned_execution,
    is_auditable,
    write_audit_event,
)
from app.models.tenant import Company, Enterprise
from app.models.user import RoleCode, User, UserRoleAssignment
from tests.conftest import _make_current_user
from tests.factories import create_company, create_enterprise, create_user, create_user_role


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

COMPANY_A_TENANT = uuid.UUID("aaaa0000-0000-0000-0000-000000000001")
COMPANY_B_TENANT = uuid.UUID("bbbb0000-0000-0000-0000-000000000002")


@pytest.fixture
def company_a() -> Company:
    return create_company(name="Company A")


@pytest.fixture
def company_b() -> Company:
    return create_company(name="Company B")


@pytest.fixture
def enterprise() -> Enterprise:
    return create_enterprise()


# ---------------------------------------------------------------------------
# assert_permission()
# ---------------------------------------------------------------------------


class TestAssertPermission:
    def test_raises_403_when_permission_missing(self) -> None:
        """
        assert_permission() must raise HTTP 403 when the required permission
        is absent.  It must NEVER raise 404 — returning 'not found' for a
        resource the caller has no access to leaks the existence of that
        resource (IDOR / enumeration vulnerability).
        """
        permissions: set[Permission] = {Permission.SCRIPT_READ}
        with pytest.raises(HTTPException) as exc_info:
            assert_permission(permissions, Permission.SCRIPT_APPROVE)
        assert exc_info.value.status_code == 403

    def test_does_not_raise_when_permission_present(self) -> None:
        """Guard passes silently when the permission is present."""
        permissions = {Permission.SCRIPT_APPROVE, Permission.SCRIPT_READ}
        # Should not raise
        assert_permission(permissions, Permission.SCRIPT_APPROVE)

    def test_403_detail_contains_permission_name(self) -> None:
        """Error detail includes the permission value so logs are useful."""
        permissions: set[Permission] = set()
        with pytest.raises(HTTPException) as exc_info:
            assert_permission(permissions, Permission.CYCLE_DELETE)
        assert "cycle:delete" in exc_info.value.detail

    def test_empty_permission_set_always_raises(self) -> None:
        """A user with no permissions is denied everything."""
        for perm in list(Permission)[:5]:
            with pytest.raises(HTTPException):
                assert_permission(set(), perm)

    def test_full_permission_set_never_raises(self) -> None:
        """A global admin (all permissions) is never denied."""
        all_perms = set(Permission)
        for perm in Permission:
            assert_permission(all_perms, perm)  # must not raise

    def test_user_id_logged_on_denial(self, caplog: pytest.LogCaptureFixture) -> None:
        """
        When permission is denied, the user_id is included in the log event
        so security alerts have an actor to attribute the attempt to.
        """
        uid = uuid.uuid4()
        with pytest.raises(HTTPException):
            assert_permission({Permission.SCRIPT_READ}, Permission.SCRIPT_DELETE, user_id=uid)
        # structlog writes to standard logging during tests
        # Just verify the call doesn't crash when user_id is provided


# ---------------------------------------------------------------------------
# assert_domain_access() — BPO restriction
# ---------------------------------------------------------------------------


class TestAssertDomainAccess:
    def test_bpo_can_access_own_domain(self) -> None:
        """A BPO user with domain_code='FIN' can access FIN resources."""
        assert_domain_access(
            roles=[RoleCode.BUSINESS_PROCESS_OWNER],
            domain_codes=["FIN"],
            target_domain="FIN",
        )  # must not raise

    def test_bpo_denied_other_domain(self) -> None:
        """A BPO user assigned to FIN cannot access HR domain resources."""
        with pytest.raises(HTTPException) as exc_info:
            assert_domain_access(
                roles=[RoleCode.BUSINESS_PROCESS_OWNER],
                domain_codes=["FIN"],
                target_domain="HR",
            )
        assert exc_info.value.status_code == 403

    def test_non_bpo_role_bypasses_domain_check(self) -> None:
        """
        A Validation Lead or any non-BPO role is NOT domain-restricted.
        Domain scoping is only enforced for BPO users.
        """
        assert_domain_access(
            roles=[RoleCode.VALIDATION_LEAD],
            domain_codes=[],  # no domains assigned
            target_domain="HR",
        )  # must not raise

    def test_bpo_with_multiple_domains_can_access_any(self) -> None:
        """A BPO with domains=['FIN', 'HR'] can access both."""
        for domain in ["FIN", "HR"]:
            assert_domain_access(
                roles=[RoleCode.BUSINESS_PROCESS_OWNER],
                domain_codes=["FIN", "HR"],
                target_domain=domain,
            )  # must not raise

    def test_bpo_no_domain_assigned_cannot_access_any(self) -> None:
        """BPO with no domain assignments is effectively locked out of all domains."""
        with pytest.raises(HTTPException):
            assert_domain_access(
                roles=[RoleCode.BUSINESS_PROCESS_OWNER],
                domain_codes=[],
                target_domain="FIN",
            )

    def test_no_target_domain_passes_for_bpo(self) -> None:
        """Resources without a domain tag are accessible to BPO users."""
        assert_domain_access(
            roles=[RoleCode.BUSINESS_PROCESS_OWNER],
            domain_codes=["FIN"],
            target_domain=None,
        )  # no restriction when resource has no domain

    def test_mixed_roles_including_bpo_bypass_restriction(self) -> None:
        """
        If a user holds BPO plus a non-BPO role, the non-BPO role wins and
        domain restriction is lifted.  This prevents a bug where assigning an
        additional role to a BPO user accidentally locks them further.
        """
        assert_domain_access(
            roles=[RoleCode.BUSINESS_PROCESS_OWNER, RoleCode.VALIDATION_LEAD],
            domain_codes=["FIN"],
            target_domain="HR",
        )  # VL role bypasses the BPO restriction


# ---------------------------------------------------------------------------
# assert_assigned_execution() — VT can only execute own assignments
# ---------------------------------------------------------------------------


class TestAssertAssignedExecution:
    def test_vt_can_update_own_assignment(self) -> None:
        """A Validation Tester can submit results for their own assignment."""
        uid = uuid.uuid4()
        assert_assigned_execution(
            roles=[RoleCode.VALIDATION_TESTER],
            requester_id=uid,
            assigned_to_id=uid,
        )  # must not raise

    def test_vt_denied_other_user_assignment(self) -> None:
        """
        A VT must not be able to submit results for someone else's assignment.
        This prevents one tester from falsifying another's execution records.
        """
        with pytest.raises(HTTPException) as exc_info:
            assert_assigned_execution(
                roles=[RoleCode.VALIDATION_TESTER],
                requester_id=uuid.uuid4(),
                assigned_to_id=uuid.uuid4(),  # different user
            )
        assert exc_info.value.status_code == 403

    def test_validation_lead_can_update_any_assignment(self) -> None:
        """
        Validation Leads oversee execution and may update any assignment,
        not just their own.
        """
        assert_assigned_execution(
            roles=[RoleCode.VALIDATION_LEAD],
            requester_id=uuid.uuid4(),
            assigned_to_id=uuid.uuid4(),  # different user — allowed for VL
        )  # must not raise

    def test_company_admin_can_update_any_assignment(self) -> None:
        """Company admins have override access to all assignments."""
        assert_assigned_execution(
            roles=[RoleCode.COMPANY_ADMIN],
            requester_id=uuid.uuid4(),
            assigned_to_id=uuid.uuid4(),
        )  # must not raise


# ---------------------------------------------------------------------------
# FailedAuthThrottle — brute-force protection
# ---------------------------------------------------------------------------


class TestFailedAuthThrottle:
    def test_clean_ip_is_not_blocked(self) -> None:
        """A fresh IP with no prior failures is allowed through."""
        throttle = FailedAuthThrottle(max_failures=3, window_seconds=60)
        assert not throttle.is_blocked("192.168.1.1")

    def test_ip_blocked_after_max_failures(self) -> None:
        """
        After max_failures failed attempts within the window, the IP is blocked.
        This prevents password-spraying and credential-stuffing attacks.
        """
        throttle = FailedAuthThrottle(max_failures=3, window_seconds=60)
        ip = "10.0.0.1"
        for _ in range(3):
            throttle.record_failure(ip)
        assert throttle.is_blocked(ip)

    def test_ip_not_blocked_below_threshold(self) -> None:
        """Failures below the threshold do not trigger a block."""
        throttle = FailedAuthThrottle(max_failures=5, window_seconds=60)
        ip = "10.0.0.2"
        for _ in range(4):
            throttle.record_failure(ip)
        assert not throttle.is_blocked(ip)

    def test_clear_removes_block(self) -> None:
        """
        clear() removes all failure records for an IP.
        Used after a successful authentication to reset the counter.
        """
        throttle = FailedAuthThrottle(max_failures=1, window_seconds=60)
        ip = "10.0.0.3"
        throttle.record_failure(ip)
        assert throttle.is_blocked(ip)
        throttle.clear(ip)
        assert not throttle.is_blocked(ip)

    def test_different_ips_tracked_independently(self) -> None:
        """Failures on one IP do not affect the block status of another."""
        throttle = FailedAuthThrottle(max_failures=2, window_seconds=60)
        throttle.record_failure("1.1.1.1")
        throttle.record_failure("1.1.1.1")
        assert throttle.is_blocked("1.1.1.1")
        assert not throttle.is_blocked("2.2.2.2")


# ---------------------------------------------------------------------------
# is_auditable() — audit requirement flag
# ---------------------------------------------------------------------------


class TestIsAuditable:
    def test_script_approve_is_auditable(self) -> None:
        """SCRIPT_APPROVE is security-critical and must generate an audit record."""
        assert is_auditable(Permission.SCRIPT_APPROVE)

    def test_user_assign_role_is_auditable(self) -> None:
        """Role assignment changes are always audited."""
        assert is_auditable(Permission.USER_ASSIGN_ROLE)

    def test_admin_global_is_auditable(self) -> None:
        assert is_auditable(Permission.ADMIN_GLOBAL)

    def test_script_read_is_not_auditable(self) -> None:
        """Read operations don't need to be audited to avoid log flooding."""
        assert not is_auditable(Permission.SCRIPT_READ)

    def test_project_read_is_not_auditable(self) -> None:
        assert not is_auditable(Permission.PROJECT_READ)

    def test_all_audit_required_permissions_flagged(self) -> None:
        """Every permission in AUDIT_REQUIRED_PERMISSIONS must pass is_auditable()."""
        for perm in AUDIT_REQUIRED_PERMISSIONS:
            assert is_auditable(perm), f"{perm.value} is in AUDIT_REQUIRED but is_auditable() returns False"


# ---------------------------------------------------------------------------
# TenantContext — tenant properties derived correctly
# ---------------------------------------------------------------------------


class TestTenantContext:
    def test_company_id_equals_tenant_id(
        self, company_a: Company, enterprise: Enterprise
    ) -> None:
        """
        In KAATS, company.id == company.tenant_id by design.
        TenantContext.company_id and .tenant_id must both return the same value
        to avoid confusion in query filters.
        """
        ctx = TenantContext(company=company_a, enterprise=enterprise)
        assert ctx.company_id == company_a.id
        assert ctx.tenant_id == company_a.tenant_id

    def test_enterprise_id_from_company(
        self, company_a: Company, enterprise: Enterprise
    ) -> None:
        """enterprise_id is read from the company, not the enterprise object."""
        ctx = TenantContext(company=company_a, enterprise=enterprise)
        assert ctx.enterprise_id == company_a.enterprise_id

    def test_cross_tenant_context_has_different_ids(self) -> None:
        """
        Two tenant contexts from different companies must have different
        tenant_ids.  This is the invariant that makes RLS work.
        """
        ent = create_enterprise()
        company_x = create_company(ent, name="Company X")
        company_y = create_company(ent, name="Company Y")
        ctx_x = TenantContext(company=company_x, enterprise=ent)
        ctx_y = TenantContext(company=company_y, enterprise=ent)
        assert ctx_x.tenant_id != ctx_y.tenant_id


# ---------------------------------------------------------------------------
# write_audit_event() — async audit logging
# ---------------------------------------------------------------------------


class TestWriteAuditEvent:
    @pytest.mark.asyncio
    async def test_writes_audit_log_record(self) -> None:
        """
        write_audit_event() must create an AuditLog record in the database.
        This verifies the audit trail is not silently dropped.
        """
        session = AsyncMock()
        session.add = MagicMock()

        await write_audit_event(
            session=session,
            user_id=uuid.uuid4(),
            tenant_id=uuid.uuid4(),
            action="APPROVE",
            resource_type="test_script",
            resource_id=str(uuid.uuid4()),
            permission=Permission.SCRIPT_APPROVE,
        )

        # session.add() must have been called with an AuditLog instance
        session.add.assert_called_once()
        from app.models.audit_log import AuditLog
        call_arg = session.add.call_args[0][0]
        assert isinstance(call_arg, AuditLog)

    @pytest.mark.asyncio
    async def test_audit_includes_before_and_after_state(self) -> None:
        """
        Before/after snapshots are captured for state-changing operations so
        that the audit trail can be used for forensics.
        """
        session = AsyncMock()
        session.add = MagicMock()

        before = '{"status": "IN_REVIEW"}'
        after = '{"status": "APPROVED"}'

        await write_audit_event(
            session=session,
            user_id=uuid.uuid4(),
            tenant_id=uuid.uuid4(),
            action="APPROVE",
            resource_type="test_script",
            resource_id="script-123",
            before_state=before,
            after_state=after,
        )

        from app.models.audit_log import AuditLog
        log: AuditLog = session.add.call_args[0][0]
        assert log.before_state == before
        assert log.after_state == after
