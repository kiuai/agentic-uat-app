"""Pydantic schema registry — all public schemas exported from here."""

from app.schemas.common import PaginatedResponse, PaginationMeta, ErrorDetail, Links
from app.schemas.tenant import (
    EnterpriseCreate, EnterpriseUpdate, EnterpriseResponse, EnterpriseRead,
    CompanyCreate, CompanyUpdate, CompanyResponse, CompanyRead,
    BusinessDomainCreate, BusinessDomainUpdate, BusinessDomainResponse,
)
from app.schemas.user import (
    UserCreate, UserUpdate, UserResponse, UserRead,
    RoleAssignmentCreate, RoleAssignmentResponse,
)
from app.schemas.project import (
    ProjectCreate, ProjectUpdate, ProjectResponse, ProjectRead,
    EnvironmentCreate, EnvironmentUpdate, EnvironmentResponse, EnvironmentRead,
)
from app.schemas.requirement import (
    RequirementCreate, RequirementUpdate, RequirementResponse, RequirementRead,
)
from app.schemas.test_script import (
    TestScriptCreate, TestScriptUpdate, TestScriptResponse, TestScriptRead,
    TestScriptVersionResponse,
    ApprovalRequest, RejectionRequest, ExportRequest, ExportResponse,
)
from app.schemas.test_cycle import (
    TestCycleCreate, TestCycleUpdate, TestCycleResponse, TestCycleRead,
    TestAssignmentCreate, TestAssignmentUpdate, TestAssignmentResponse,
    TestResultCreate, TestResultResponse,
    EvidenceResponse, EvidenceRead,
    ExecutionCreate, ExecutionUpdate, ExecutionRead,
)
from app.schemas.crawl_job import (
    CrawlJobCreate, CrawlJobResponse,
    CrawlPageResponse,
)
from app.schemas.job import JobResponse, JobRead, JobStatus, JobType
from app.schemas.defect import DefectCreate, DefectUpdate, DefectResponse, DefectRead
from app.schemas.ai_generation import GenerationJobRequest, CrawlJobRequest

__all__ = [
    # Common
    "PaginatedResponse", "PaginationMeta", "ErrorDetail", "Links",
    # Tenancy
    "EnterpriseCreate", "EnterpriseUpdate", "EnterpriseResponse", "EnterpriseRead",
    "CompanyCreate", "CompanyUpdate", "CompanyResponse", "CompanyRead",
    "BusinessDomainCreate", "BusinessDomainUpdate", "BusinessDomainResponse",
    # Users
    "UserCreate", "UserUpdate", "UserResponse", "UserRead",
    "RoleAssignmentCreate", "RoleAssignmentResponse",
    # Projects
    "ProjectCreate", "ProjectUpdate", "ProjectResponse", "ProjectRead",
    "EnvironmentCreate", "EnvironmentUpdate", "EnvironmentResponse", "EnvironmentRead",
    # Requirements
    "RequirementCreate", "RequirementUpdate", "RequirementResponse", "RequirementRead",
    # Test scripts
    "TestScriptCreate", "TestScriptUpdate", "TestScriptResponse", "TestScriptRead",
    "TestScriptVersionResponse",
    "ApprovalRequest", "RejectionRequest", "ExportRequest", "ExportResponse",
    # Test cycles & execution
    "TestCycleCreate", "TestCycleUpdate", "TestCycleResponse", "TestCycleRead",
    "TestAssignmentCreate", "TestAssignmentUpdate", "TestAssignmentResponse",
    "TestResultCreate", "TestResultResponse",
    "EvidenceResponse", "EvidenceRead",
    "ExecutionCreate", "ExecutionUpdate", "ExecutionRead",
    # Crawl
    "CrawlJobCreate", "CrawlJobResponse",
    "CrawlPageResponse",
    # Jobs
    "JobResponse", "JobRead", "JobStatus", "JobType",
    # Defects
    "DefectCreate", "DefectUpdate", "DefectResponse", "DefectRead",
    # AI / Crawler requests
    "GenerationJobRequest", "CrawlJobRequest",
]
