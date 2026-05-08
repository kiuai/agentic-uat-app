"""
Permission definitions and role-to-permission mappings.

This is the authoritative source for the RBAC matrix documented in
/docs/RBAC_MATRIX.md. Any change here must be reflected there.

Permission names follow the pattern NOUN_VERB to make permission checks
read naturally: ``user.has_permission(Permission.SCRIPT_APPROVE)``.
"""

from __future__ import annotations

from enum import Enum

from app.models.user import RoleCode

# Backward-compat alias — code that imported UserRole as the role enum continues to work
UserRole = RoleCode


class Permission(str, Enum):
    # ── Tenant Management ──────────────────────────────────────────────────
    TENANT_READ = "tenant:read"
    TENANT_CREATE = "tenant:create"
    TENANT_UPDATE = "tenant:update"
    TENANT_DELETE = "tenant:delete"

    # ── User Management ────────────────────────────────────────────────────
    USER_READ = "user:read"
    USER_CREATE = "user:create"
    USER_UPDATE = "user:update"
    USER_DELETE = "user:delete"
    USER_ASSIGN_ROLE = "user:assign_role"

    # ── Project Management ─────────────────────────────────────────────────
    PROJECT_READ = "project:read"
    PROJECT_CREATE = "project:create"
    PROJECT_UPDATE = "project:update"
    PROJECT_DELETE = "project:delete"

    # ── Requirements ───────────────────────────────────────────────────────
    REQUIREMENT_READ = "requirement:read"
    REQUIREMENT_CREATE = "requirement:create"
    REQUIREMENT_UPDATE = "requirement:update"
    REQUIREMENT_DELETE = "requirement:delete"

    # ── Test Scripts ───────────────────────────────────────────────────────
    SCRIPT_READ = "script:read"
    SCRIPT_CREATE = "script:create"
    SCRIPT_UPDATE = "script:update"
    SCRIPT_DELETE = "script:delete"
    SCRIPT_APPROVE = "script:approve"
    SCRIPT_EXPORT = "script:export"
    SCRIPT_IMPORT = "script:import"

    # ── Test Cycles & Execution ────────────────────────────────────────────
    CYCLE_READ = "cycle:read"
    CYCLE_CREATE = "cycle:create"
    CYCLE_UPDATE = "cycle:update"
    CYCLE_DELETE = "cycle:delete"
    ASSIGNMENT_CREATE = "assignment:create"
    ASSIGNMENT_UPDATE = "assignment:update"
    RESULT_CREATE = "result:create"
    RESULT_UPDATE = "result:update"
    RESULT_READ = "result:read"

    # ── Crawler ────────────────────────────────────────────────────────────
    CRAWLER_READ = "crawler:read"
    CRAWLER_CREATE = "crawler:create"
    CRAWLER_CANCEL = "crawler:cancel"

    # ── AI Generation ──────────────────────────────────────────────────────
    AI_GENERATE = "ai:generate"
    AI_CONFIGURE = "ai:configure"

    # ── Reports ────────────────────────────────────────────────────────────
    REPORT_READ = "report:read"
    REPORT_EXPORT = "report:export"

    # ── Administration ─────────────────────────────────────────────────────
    ADMIN_GLOBAL = "admin:global"
    ADMIN_ENTERPRISE = "admin:enterprise"
    ADMIN_COMPANY = "admin:company"
    AUDIT_LOG_READ = "audit_log:read"


_ALL = set(Permission)

# Permissions available to every authenticated user regardless of role
_BASE: set[Permission] = {
    Permission.PROJECT_READ,
    Permission.REQUIREMENT_READ,
    Permission.SCRIPT_READ,
    Permission.CYCLE_READ,
    Permission.RESULT_READ,
    Permission.CRAWLER_READ,
    Permission.REPORT_READ,
}

ROLE_PERMISSIONS: dict[RoleCode, set[Permission]] = {

    RoleCode.GLOBAL_ADMIN: _ALL,

    RoleCode.ENTERPRISE_ADMIN: _ALL - {Permission.ADMIN_GLOBAL},

    RoleCode.COMPANY_ADMIN: _ALL - {
        Permission.ADMIN_GLOBAL,
        Permission.ADMIN_ENTERPRISE,
        Permission.TENANT_CREATE,
        Permission.TENANT_DELETE,
    },

    RoleCode.SYSTEM_MANAGER: {
        # Projects
        Permission.PROJECT_READ, Permission.PROJECT_CREATE,
        Permission.PROJECT_UPDATE, Permission.PROJECT_DELETE,
        # Requirements
        Permission.REQUIREMENT_READ, Permission.REQUIREMENT_CREATE,
        Permission.REQUIREMENT_UPDATE, Permission.REQUIREMENT_DELETE,
        # Scripts
        Permission.SCRIPT_READ, Permission.SCRIPT_CREATE,
        Permission.SCRIPT_UPDATE, Permission.SCRIPT_DELETE,
        Permission.SCRIPT_IMPORT, Permission.SCRIPT_EXPORT,
        # Cycles
        Permission.CYCLE_READ, Permission.CYCLE_CREATE,
        Permission.CYCLE_UPDATE, Permission.CYCLE_DELETE,
        Permission.ASSIGNMENT_CREATE, Permission.ASSIGNMENT_UPDATE,
        Permission.RESULT_READ,
        # Crawler
        Permission.CRAWLER_READ, Permission.CRAWLER_CREATE, Permission.CRAWLER_CANCEL,
        # AI
        Permission.AI_GENERATE, Permission.AI_CONFIGURE,
        # Reporting
        Permission.REPORT_READ, Permission.REPORT_EXPORT,
        # Users (read-only)
        Permission.USER_READ,
        Permission.AUDIT_LOG_READ,
    },

    RoleCode.VALIDATION_LEAD: {
        # Projects & Cycles
        Permission.PROJECT_READ,
        Permission.CYCLE_READ, Permission.CYCLE_CREATE,
        Permission.CYCLE_UPDATE, Permission.CYCLE_DELETE,
        Permission.ASSIGNMENT_CREATE, Permission.ASSIGNMENT_UPDATE,
        # Scripts
        Permission.SCRIPT_READ, Permission.SCRIPT_CREATE,
        Permission.SCRIPT_UPDATE, Permission.SCRIPT_APPROVE,
        Permission.SCRIPT_EXPORT,
        # Requirements
        Permission.REQUIREMENT_READ, Permission.REQUIREMENT_CREATE,
        Permission.REQUIREMENT_UPDATE,
        # Results
        Permission.RESULT_READ,
        # Reports
        Permission.REPORT_READ, Permission.REPORT_EXPORT,
        # Crawler (trigger only)
        Permission.CRAWLER_READ, Permission.CRAWLER_CREATE,
        # AI generation
        Permission.AI_GENERATE,
        Permission.AUDIT_LOG_READ,
    },

    RoleCode.QA: {
        Permission.PROJECT_READ,
        Permission.REQUIREMENT_READ,
        Permission.SCRIPT_READ, Permission.SCRIPT_EXPORT,
        Permission.CYCLE_READ,
        Permission.ASSIGNMENT_UPDATE,
        Permission.RESULT_CREATE, Permission.RESULT_UPDATE, Permission.RESULT_READ,
        Permission.CRAWLER_READ,
        Permission.REPORT_READ,
    },

    RoleCode.VALIDATION_TESTER: {
        Permission.PROJECT_READ,
        Permission.REQUIREMENT_READ,
        # Own draft scripts only — enforced at service layer
        Permission.SCRIPT_READ, Permission.SCRIPT_CREATE, Permission.SCRIPT_UPDATE,
        Permission.SCRIPT_EXPORT,
        Permission.CYCLE_READ,
        # Own assignment only — enforced at service layer
        Permission.ASSIGNMENT_UPDATE,
        Permission.RESULT_CREATE, Permission.RESULT_READ,
        Permission.REPORT_READ,
    },

    RoleCode.BUSINESS_PROCESS_OWNER: {
        # Domain-scoped — service layer enforces domain_code filtering
        Permission.REQUIREMENT_READ,
        Permission.SCRIPT_READ,
        Permission.SCRIPT_APPROVE,  # Domain-scoped only
        Permission.CYCLE_READ,
        Permission.RESULT_READ,
        Permission.REPORT_READ, Permission.REPORT_EXPORT,
    },
}


def has_permission(role: RoleCode, permission: Permission) -> bool:
    """Check if a single role grants the given permission."""
    return permission in ROLE_PERMISSIONS.get(role, set())


def permissions_for_roles(roles: list[RoleCode]) -> set[Permission]:
    """Return the union permission set for a list of roles."""
    perms: set[Permission] = set()
    for role in roles:
        perms |= ROLE_PERMISSIONS.get(role, set())
    return perms


# ---------------------------------------------------------------------------
# Sensitive permissions that trigger audit log writes
# ---------------------------------------------------------------------------

AUDIT_REQUIRED_PERMISSIONS = frozenset({
    Permission.SCRIPT_APPROVE,
    Permission.SCRIPT_DELETE,
    Permission.USER_ASSIGN_ROLE,
    Permission.USER_DELETE,
    Permission.ADMIN_GLOBAL,
    Permission.ADMIN_ENTERPRISE,
    Permission.ADMIN_COMPANY,
    Permission.TENANT_CREATE,
    Permission.TENANT_DELETE,
    Permission.CYCLE_DELETE,
})
