"""ORM model registry — import all models here so Alembic autogenerate sees them."""

from app.models.base import TenantAwareBase, TimestampMixin, TenantMixin
from app.models.global_config import GlobalConfig
from app.models.tenant import Enterprise, Company, BusinessDomain
from app.models.user import User, UserRoleAssignment, RoleCode, UserRole
from app.models.project import Project, Environment, SystemType, ProjectStatus, EnvironmentType
from app.models.requirement import Requirement, RequirementSourceType, RequirementStatus, RequirementPriority
from app.models.test_script import TestScript, TestScriptVersion, ScriptStatus, ScriptFormat
from app.models.test_cycle import TestCycle, TestAssignment, TestResult, ExecutionEvidence, CycleStatus, ExecutionStatus
from app.models.crawl_job import CrawlJob, CrawlPage, CrawlerType, CrawlAuthType, CrawlJobStatus
from app.models.job import Job, JobType, JobStatus
from app.models.defect import Defect, DefectSeverity, DefectStatus
from app.models.audit_log import AuditLog

__all__ = [
    # Base classes
    "TenantAwareBase",
    "TimestampMixin",
    "TenantMixin",
    # System config
    "GlobalConfig",
    # Tenancy
    "Enterprise",
    "Company",
    "BusinessDomain",
    # Users & RBAC
    "User",
    "UserRoleAssignment",
    "RoleCode",
    "UserRole",  # backward-compat alias for RoleCode
    # Projects
    "Project",
    "Environment",
    "SystemType",
    "ProjectStatus",
    "EnvironmentType",
    # Requirements
    "Requirement",
    "RequirementSourceType",
    "RequirementStatus",
    "RequirementPriority",
    # Test scripts
    "TestScript",
    "TestScriptVersion",
    "ScriptStatus",
    "ScriptFormat",
    # Test cycles & execution
    "TestCycle",
    "TestAssignment",
    "TestResult",
    "ExecutionEvidence",
    "CycleStatus",
    "ExecutionStatus",
    # Crawling
    "CrawlJob",
    "CrawlPage",
    "CrawlerType",
    "CrawlAuthType",
    "CrawlJobStatus",
    # Jobs
    "Job",
    "JobType",
    "JobStatus",
    # Defects
    "Defect",
    "DefectSeverity",
    "DefectStatus",
    # Audit
    "AuditLog",
]
