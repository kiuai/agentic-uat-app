"""
Test data factories for KAATS.

Plain-Python factories that produce in-memory model instances without hitting
any database.  Use these in unit tests where you need valid objects but don't
care about persistence.

For integration tests that need persisted rows, call the factory and then
``db_session.add(obj); await db_session.flush()``.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from typing import Any

from app.models.crawl_job import (
    CrawlAuthType,
    CrawlJob,
    CrawlJobStatus,
    CrawlPage,
    CrawlerType,
)
from app.models.project import Project, ProjectStatus, SystemType
from app.models.requirement import (
    Requirement,
    RequirementPriority,
    RequirementSourceType,
    RequirementStatus,
)
from app.models.tenant import BusinessDomain, Company, Enterprise
from app.models.test_cycle import (
    CycleStatus,
    ExecutionStatus,
    TestAssignment,
    TestCycle,
    TestResult,
)
from app.models.test_script import ScriptFormat, ScriptStatus, TestScript
from app.models.user import RoleCode, User, UserRoleAssignment


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _uuid() -> uuid.UUID:
    return uuid.uuid4()


def _now() -> datetime:
    return datetime.now(tz=timezone.utc)


def _set_attrs(obj: Any, **kwargs: Any) -> Any:
    """Set attributes on a newly constructed model instance."""
    for k, v in kwargs.items():
        setattr(obj, k, v)
    return obj


# ---------------------------------------------------------------------------
# Tenant factories
# ---------------------------------------------------------------------------


def create_enterprise(
    *,
    name: str = "Acme Corp",
    slug: str | None = None,
    is_active: bool = True,
    azure_ad_tenant_id: str | None = None,
) -> Enterprise:
    """
    Create an in-memory Enterprise instance.

    The enterprise represents the top-level organisational unit (a SaaS customer).
    ``azure_ad_tenant_id`` links it to a real Azure AD tenant for SSO.
    """
    eid = _uuid()
    e = Enterprise.__new__(Enterprise)
    return _set_attrs(
        e,
        id=eid,
        name=name,
        slug=slug or f"enterprise-{eid.hex[:8]}",
        is_active=is_active,
        azure_ad_tenant_id=azure_ad_tenant_id,
        settings=None,
        created_at=_now(),
        updated_at=_now(),
        companies=[],
    )


def create_company(
    enterprise: Enterprise | None = None,
    *,
    name: str = "Acme Operations",
    slug: str | None = None,
    is_active: bool = True,
) -> Company:
    """
    Create an in-memory Company instance.

    Company = tenant.  ``tenant_id`` is the same as ``id`` by design; this is
    the value passed as ``X-Tenant-ID`` in API requests.
    """
    enterprise = enterprise or create_enterprise()
    cid = _uuid()
    c = Company.__new__(Company)
    return _set_attrs(
        c,
        id=cid,
        tenant_id=cid,  # Company.id == Company.tenant_id by convention
        enterprise_id=enterprise.id,
        enterprise=enterprise,
        name=name,
        slug=slug or f"company-{cid.hex[:8]}",
        is_active=is_active,
        settings=None,
        created_at=_now(),
        updated_at=_now(),
        business_domains=[],
    )


def create_business_domain(
    company: Company | None = None,
    *,
    name: str = "Finance",
    code: str = "FIN",
    is_active: bool = True,
) -> BusinessDomain:
    """Create an in-memory BusinessDomain used for BPO scoping."""
    company = company or create_company()
    bd = BusinessDomain.__new__(BusinessDomain)
    return _set_attrs(
        bd,
        id=_uuid(),
        tenant_id=company.tenant_id,
        company=company,
        name=name,
        code=code,
        description=None,
        is_active=is_active,
        created_at=_now(),
        updated_at=_now(),
    )


# ---------------------------------------------------------------------------
# User factories
# ---------------------------------------------------------------------------


def create_user(
    *,
    email: str | None = None,
    display_name: str | None = None,
    is_global_admin: bool = False,
    is_active: bool = True,
) -> User:
    """Create an in-memory User.  No roles are attached; see create_user_role."""
    uid = _uuid()
    u = User.__new__(User)
    return _set_attrs(
        u,
        id=uid,
        azure_oid=str(_uuid()),
        email=email or f"user-{uid.hex[:6]}@example.com",
        display_name=display_name or f"Test User {uid.hex[:6]}",
        is_active=is_active,
        is_global_admin=is_global_admin,
        last_login_at=None,
        created_at=_now(),
        updated_at=_now(),
        role_assignments=[],
    )


def create_user_role(
    user: User | None = None,
    company: Company | None = None,
    *,
    role: RoleCode = RoleCode.VALIDATION_TESTER,
    domain_code: str | None = None,
    assigned_by: uuid.UUID | None = None,
) -> UserRoleAssignment:
    """
    Attach a role to a user within a specific tenant (company).

    ``domain_code`` is only meaningful for BPO roles; it restricts the
    assignment to a single business domain.
    """
    user = user or create_user()
    company = company or create_company()
    ra = UserRoleAssignment.__new__(UserRoleAssignment)
    return _set_attrs(
        ra,
        id=_uuid(),
        user_id=user.id,
        tenant_id=company.tenant_id,
        role=role,
        domain_code=domain_code,
        created_at=_now(),
        assigned_by=assigned_by,
    )


# ---------------------------------------------------------------------------
# Project factories
# ---------------------------------------------------------------------------


def create_project(
    company: Company | None = None,
    *,
    name: str = "Test Project",
    status: ProjectStatus = ProjectStatus.ACTIVE,
    system_type: SystemType = SystemType.WEB,
    base_url: str | None = "https://app.example.com",
    created_by: uuid.UUID | None = None,
) -> Project:
    """Create an in-memory Project with sensible defaults."""
    company = company or create_company()
    p = Project.__new__(Project)
    return _set_attrs(
        p,
        id=_uuid(),
        tenant_id=company.tenant_id,
        name=name,
        description="A test project",
        status=status,
        system_type=system_type,
        base_url=base_url,
        settings=None,
        created_by=created_by or _uuid(),
        created_at=_now(),
        updated_at=_now(),
        environments=[],
        requirements=[],
        jobs=[],
        test_cycles=[],
        crawl_jobs=[],
    )


# ---------------------------------------------------------------------------
# Requirement factories
# ---------------------------------------------------------------------------


def create_requirement(
    project: Project | None = None,
    *,
    title: str = "User Login",
    content_text: str = "The system shall allow users to log in with their email and password.",
    status: RequirementStatus = RequirementStatus.PROCESSED,
    priority: RequirementPriority = RequirementPriority.HIGH,
    business_domain: str | None = None,
    uploaded_by: uuid.UUID | None = None,
) -> Requirement:
    """Create an in-memory Requirement linked to a project."""
    project = project or create_project()
    r = Requirement.__new__(Requirement)
    return _set_attrs(
        r,
        id=_uuid(),
        tenant_id=project.tenant_id,
        project_id=project.id,
        project=project,
        title=title,
        description=None,
        source_type=RequirementSourceType.TEXT,
        source_ref=None,
        content_text=content_text,
        blob_uri=None,
        status=status,
        business_domain=business_domain,
        priority=priority,
        tags=None,
        uploaded_by=uploaded_by or _uuid(),
        created_at=_now(),
        updated_at=_now(),
        test_scripts=[],
    )


# ---------------------------------------------------------------------------
# Test script factories
# ---------------------------------------------------------------------------


def create_test_script(
    project: Project | None = None,
    requirement: Requirement | None = None,
    *,
    title: str = "Login Script",
    format: ScriptFormat = ScriptFormat.GHERKIN,
    status: ScriptStatus = ScriptStatus.DRAFT,
    is_ai_generated: bool = False,
    cosmos_doc_id: str | None = None,
    created_by: uuid.UUID | None = None,
) -> TestScript:
    """
    Create an in-memory TestScript (metadata only; content lives in Cosmos DB).

    ``cosmos_doc_id`` is the Cosmos document pointer; in unit tests leave it
    as None unless you're testing Cosmos integration specifically.
    """
    project = project or create_project()
    requirement = requirement or create_requirement(project)
    ts = TestScript.__new__(TestScript)
    return _set_attrs(
        ts,
        id=_uuid(),
        tenant_id=project.tenant_id,
        project_id=project.id,
        requirement_id=requirement.id,
        requirement=requirement,
        title=title,
        description=None,
        format=format,
        status=status,
        cosmos_doc_id=cosmos_doc_id or str(_uuid()),
        current_version=1,
        is_ai_generated=is_ai_generated,
        approved_by=None,
        created_by=created_by or _uuid(),
        created_at=_now(),
        updated_at=_now(),
        versions=[],
        assignments=[],
    )


# ---------------------------------------------------------------------------
# Crawl job factories
# ---------------------------------------------------------------------------


def create_crawl_job(
    project: Project | None = None,
    *,
    status: CrawlJobStatus = CrawlJobStatus.PENDING,
    crawler_type: CrawlerType = CrawlerType.WEB,
    target_url: str = "https://app.example.com",
    max_pages: int = 10,
    generate_scripts: bool = False,
    created_by: uuid.UUID | None = None,
) -> CrawlJob:
    """Create an in-memory CrawlJob.  pages relationship starts empty."""
    project = project or create_project()
    cj = CrawlJob.__new__(CrawlJob)
    return _set_attrs(
        cj,
        id=_uuid(),
        tenant_id=project.tenant_id,
        project_id=project.id,
        project=project,
        crawler_type=crawler_type,
        status=status,
        target_url=target_url,
        launchpad_url=None,
        max_pages=max_pages,
        auth_type=CrawlAuthType.NONE,
        auth_config=None,
        generate_scripts=generate_scripts,
        created_by=created_by or _uuid(),
        started_at=None,
        completed_at=None,
        pages_found=None,
        scripts_generated=None,
        error_message=None,
        created_at=_now(),
        updated_at=_now(),
        pages=[],
    )


def create_crawl_page(
    crawl_job: CrawlJob | None = None,
    *,
    url: str = "https://app.example.com/login",
    title: str = "Login Page",
    depth: int = 0,
    elements_json: str | None = None,
) -> CrawlPage:
    """Create an in-memory CrawlPage representing one crawled URL."""
    crawl_job = crawl_job or create_crawl_job()
    cp = CrawlPage.__new__(CrawlPage)
    return _set_attrs(
        cp,
        id=_uuid(),
        tenant_id=crawl_job.tenant_id,
        crawl_job_id=crawl_job.id,
        crawl_job=crawl_job,
        url=url,
        title=title,
        page_hash=None,
        depth=depth,
        elements_json=elements_json,
        screenshot_uri=None,
        generated_script_id=None,
        created_at=_now(),
        updated_at=_now(),
    )


# ---------------------------------------------------------------------------
# Test cycle factories
# ---------------------------------------------------------------------------


def create_test_cycle(
    project: Project | None = None,
    *,
    name: str = "Sprint 1 UAT",
    status: CycleStatus = CycleStatus.DRAFT,
    created_by: uuid.UUID | None = None,
    environment_id: uuid.UUID | None = None,
) -> TestCycle:
    """Create an in-memory TestCycle."""
    project = project or create_project()
    tc = TestCycle.__new__(TestCycle)
    return _set_attrs(
        tc,
        id=_uuid(),
        tenant_id=project.tenant_id,
        project_id=project.id,
        project=project,
        environment_id=environment_id or _uuid(),
        name=name,
        description=None,
        status=status,
        created_by=created_by or _uuid(),
        lead_user_id=None,
        planned_start_date=date.today(),
        planned_end_date=None,
        actual_start_date=None,
        actual_end_date=None,
        bpo_approved_by=None,
        bpo_approved_at=None,
        created_at=_now(),
        updated_at=_now(),
        assignments=[],
    )


def create_test_assignment(
    cycle: TestCycle | None = None,
    script: TestScript | None = None,
    *,
    assigned_to: uuid.UUID | None = None,
    assigned_by: uuid.UUID | None = None,
    status: ExecutionStatus = ExecutionStatus.NOT_STARTED,
) -> TestAssignment:
    """
    Create an in-memory TestAssignment linking a script to a tester in a cycle.

    ``script_version`` is pinned at assignment time; changes to the script
    after assignment don't affect the assignment.
    """
    cycle = cycle or create_test_cycle()
    script = script or create_test_script()
    ta = TestAssignment.__new__(TestAssignment)
    return _set_attrs(
        ta,
        id=_uuid(),
        tenant_id=cycle.tenant_id,
        cycle_id=cycle.id,
        cycle=cycle,
        script_id=script.id,
        script=script,
        script_version=script.current_version,
        assigned_to=assigned_to or _uuid(),
        assigned_by=assigned_by or _uuid(),
        status=status,
        due_date=None,
        notes=None,
        created_at=_now(),
        updated_at=_now(),
        result=None,
    )


def create_test_result(
    assignment: TestAssignment | None = None,
    *,
    status: ExecutionStatus = ExecutionStatus.PASSED,
    executed_by: uuid.UUID | None = None,
    duration_seconds: int | None = 120,
    notes: str | None = None,
) -> TestResult:
    """Create an in-memory TestResult for a completed test execution."""
    assignment = assignment or create_test_assignment()
    tr = TestResult.__new__(TestResult)
    return _set_attrs(
        tr,
        id=_uuid(),
        tenant_id=assignment.tenant_id,
        assignment_id=assignment.id,
        assignment=assignment,
        status=status,
        executed_by=executed_by or assignment.assigned_to,
        executed_at=_now(),
        duration_seconds=duration_seconds,
        notes=notes,
        step_results=None,
        created_at=_now(),
        updated_at=_now(),
        evidence=[],
        defects=[],
    )
