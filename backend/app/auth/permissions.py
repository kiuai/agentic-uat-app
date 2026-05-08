"""
Permission definitions and role-to-permission mappings.

This is the authoritative source for the RBAC matrix documented in
/docs/RBAC_MATRIX.md. Any change here should be reflected there.
"""

from __future__ import annotations

from enum import Enum

from app.models.user import UserRole


class Permission(str, Enum):
    # Tenant & User Management
    ENTERPRISE_MANAGE = "enterprise:manage"
    ENTERPRISE_READ = "enterprise:read"
    COMPANY_MANAGE = "company:manage"
    COMPANY_READ = "company:read"
    USER_MANAGE = "user:manage"
    USER_READ = "user:read"
    ROLE_ASSIGN = "role:assign"
    AUDIT_LOG_READ = "audit_log:read"

    # Projects & Environments
    PROJECT_CREATE = "project:create"
    PROJECT_READ = "project:read"
    PROJECT_UPDATE = "project:update"
    PROJECT_DELETE = "project:delete"
    ENVIRONMENT_MANAGE = "environment:manage"
    ENVIRONMENT_READ = "environment:read"

    # Requirements
    REQUIREMENT_CREATE = "requirement:create"
    REQUIREMENT_READ = "requirement:read"
    REQUIREMENT_UPDATE = "requirement:update"
    REQUIREMENT_DELETE = "requirement:delete"
    REQUIREMENT_IMPORT = "requirement:import"

    # AI Generation
    AI_GENERATION_TRIGGER = "ai_generation:trigger"
    AI_GENERATION_READ = "ai_generation:read"
    AI_GENERATION_CONFIGURE = "ai_generation:configure"

    # Crawler
    CRAWLER_CONFIGURE = "crawler:configure"
    CRAWLER_TRIGGER = "crawler:trigger"
    CRAWLER_READ = "crawler:read"

    # Test Scripts
    SCRIPT_CREATE = "script:create"
    SCRIPT_READ = "script:read"
    SCRIPT_UPDATE = "script:update"
    SCRIPT_DELETE = "script:delete"
    SCRIPT_SUBMIT = "script:submit"
    SCRIPT_APPROVE = "script:approve"
    SCRIPT_EXPORT = "script:export"

    # Test Cycles & Executions
    CYCLE_CREATE = "cycle:create"
    CYCLE_READ = "cycle:read"
    CYCLE_UPDATE = "cycle:update"
    CYCLE_DELETE = "cycle:delete"
    EXECUTION_RUN = "execution:run"
    EXECUTION_LOG = "execution:log"
    EXECUTION_EVIDENCE_UPLOAD = "execution:evidence:upload"
    EXECUTION_OVERRIDE = "execution:override"

    # Defects
    DEFECT_CREATE = "defect:create"
    DEFECT_READ = "defect:read"
    DEFECT_UPDATE = "defect:update"
    DEFECT_DELETE = "defect:delete"

    # Reports
    REPORT_READ = "report:read"
    REPORT_EXPORT = "report:export"
    REPORT_SCHEDULE = "report:schedule"


# Full permission set — convenience alias
_ALL = set(Permission)

# Per-role permission sets
RolePermissions: dict[UserRole, set[Permission]] = {
    UserRole.GLOBAL_ADMIN: _ALL,

    UserRole.ENTERPRISE_ADMIN: _ALL - {
        Permission.ENTERPRISE_MANAGE,  # Can't create/delete other enterprises
    },

    UserRole.COMPANY_ADMIN: _ALL - {
        Permission.ENTERPRISE_MANAGE,
        Permission.ENTERPRISE_READ,
        Permission.COMPANY_MANAGE,
    },

    UserRole.SYSTEM_MANAGER: {
        Permission.PROJECT_CREATE,
        Permission.PROJECT_READ,
        Permission.PROJECT_UPDATE,
        Permission.PROJECT_DELETE,
        Permission.ENVIRONMENT_MANAGE,
        Permission.ENVIRONMENT_READ,
        Permission.USER_READ,
        Permission.REQUIREMENT_CREATE,
        Permission.REQUIREMENT_READ,
        Permission.REQUIREMENT_UPDATE,
        Permission.REQUIREMENT_DELETE,
        Permission.REQUIREMENT_IMPORT,
        Permission.AI_GENERATION_TRIGGER,
        Permission.AI_GENERATION_READ,
        Permission.AI_GENERATION_CONFIGURE,
        Permission.CRAWLER_CONFIGURE,
        Permission.CRAWLER_TRIGGER,
        Permission.CRAWLER_READ,
        Permission.SCRIPT_CREATE,
        Permission.SCRIPT_READ,
        Permission.SCRIPT_UPDATE,
        Permission.SCRIPT_DELETE,
        Permission.SCRIPT_SUBMIT,
        Permission.SCRIPT_APPROVE,
        Permission.SCRIPT_EXPORT,
        Permission.CYCLE_CREATE,
        Permission.CYCLE_READ,
        Permission.CYCLE_UPDATE,
        Permission.CYCLE_DELETE,
        Permission.EXECUTION_RUN,
        Permission.EXECUTION_LOG,
        Permission.EXECUTION_EVIDENCE_UPLOAD,
        Permission.EXECUTION_OVERRIDE,
        Permission.DEFECT_CREATE,
        Permission.DEFECT_READ,
        Permission.DEFECT_UPDATE,
        Permission.DEFECT_DELETE,
        Permission.REPORT_READ,
        Permission.REPORT_EXPORT,
        Permission.REPORT_SCHEDULE,
        Permission.AUDIT_LOG_READ,
    },

    UserRole.VALIDATION_LEAD: {
        Permission.PROJECT_READ,
        Permission.ENVIRONMENT_READ,
        Permission.REQUIREMENT_CREATE,
        Permission.REQUIREMENT_READ,
        Permission.REQUIREMENT_UPDATE,
        Permission.REQUIREMENT_IMPORT,
        Permission.AI_GENERATION_TRIGGER,
        Permission.AI_GENERATION_READ,
        Permission.CRAWLER_TRIGGER,
        Permission.CRAWLER_READ,
        Permission.SCRIPT_CREATE,
        Permission.SCRIPT_READ,
        Permission.SCRIPT_UPDATE,
        Permission.SCRIPT_SUBMIT,
        Permission.SCRIPT_APPROVE,
        Permission.SCRIPT_EXPORT,
        Permission.CYCLE_CREATE,
        Permission.CYCLE_READ,
        Permission.CYCLE_UPDATE,
        Permission.EXECUTION_RUN,
        Permission.EXECUTION_LOG,
        Permission.EXECUTION_EVIDENCE_UPLOAD,
        Permission.EXECUTION_OVERRIDE,
        Permission.DEFECT_CREATE,
        Permission.DEFECT_READ,
        Permission.DEFECT_UPDATE,
        Permission.REPORT_READ,
        Permission.REPORT_EXPORT,
    },

    UserRole.QA: {
        Permission.PROJECT_READ,
        Permission.ENVIRONMENT_READ,
        Permission.REQUIREMENT_READ,
        Permission.AI_GENERATION_READ,
        Permission.CRAWLER_READ,
        Permission.SCRIPT_READ,
        Permission.SCRIPT_EXPORT,
        Permission.CYCLE_READ,
        Permission.EXECUTION_RUN,
        Permission.EXECUTION_LOG,
        Permission.EXECUTION_EVIDENCE_UPLOAD,
        Permission.DEFECT_CREATE,
        Permission.DEFECT_READ,
        Permission.DEFECT_UPDATE,
        Permission.REPORT_READ,
        Permission.REPORT_EXPORT,
    },

    UserRole.VALIDATION_TESTER: {
        Permission.PROJECT_READ,
        Permission.ENVIRONMENT_READ,
        Permission.REQUIREMENT_CREATE,
        Permission.REQUIREMENT_READ,
        Permission.REQUIREMENT_UPDATE,
        Permission.AI_GENERATION_TRIGGER,
        Permission.AI_GENERATION_READ,
        Permission.SCRIPT_CREATE,
        Permission.SCRIPT_READ,
        Permission.SCRIPT_UPDATE,
        Permission.SCRIPT_SUBMIT,
        Permission.SCRIPT_EXPORT,  # Assigned scripts only — enforced in service layer
        Permission.CYCLE_READ,
        Permission.EXECUTION_RUN,   # Assigned scripts only
        Permission.EXECUTION_LOG,   # Assigned scripts only
        Permission.EXECUTION_EVIDENCE_UPLOAD,
        Permission.DEFECT_CREATE,
        Permission.DEFECT_READ,
        Permission.DEFECT_UPDATE,
        Permission.REPORT_READ,
    },

    UserRole.BUSINESS_PROCESS_OWNER: {
        Permission.PROJECT_READ,
        Permission.REQUIREMENT_READ,
        Permission.SCRIPT_READ,
        Permission.SCRIPT_APPROVE,  # Domain-scoped — enforced in service layer
        Permission.CYCLE_READ,
        Permission.DEFECT_READ,
        Permission.REPORT_READ,
        Permission.REPORT_EXPORT,
    },
}


def has_permission(role: UserRole, permission: Permission) -> bool:
    return permission in RolePermissions.get(role, set())
