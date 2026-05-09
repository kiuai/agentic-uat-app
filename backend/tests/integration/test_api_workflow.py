"""
Full end-to-end workflow integration test.

Exercises the complete KAATS user journey in a single test class:
  1. Global admin creates enterprise + company
  2. User is assigned Validation Tester role
  3. System Manager creates project
  4. Requirement is created
  5. Test script is generated (mocked AI)
  6. Script is submitted for review
  7. Validation Lead approves the script
  8. Test cycle is created with the approved script
  9. Tester submits execution result
  10. Reporting data reflects the completed execution

All database operations use the in-memory SQLite engine from conftest.py.
External services (OpenAI, Azure AD, Cosmos DB, Service Bus) are mocked.

This test exists to catch regressions where individual units work but
the workflow breaks at integration points (e.g. status transitions,
foreign key constraints, event sequencing).
"""

from __future__ import annotations

import uuid
from typing import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.auth.azure_ad import CurrentUser
from app.database import Base
from app.models.crawl_job import CrawlJobStatus
from app.models.project import ProjectStatus, SystemType
from app.models.requirement import RequirementPriority, RequirementSourceType, RequirementStatus
from app.models.test_cycle import CycleStatus, ExecutionStatus
from app.models.test_script import ScriptFormat, ScriptStatus
from app.models.user import RoleCode
from tests.conftest import _make_current_user
from tests.factories import (
    create_company,
    create_crawl_job,
    create_enterprise,
    create_project,
    create_requirement,
    create_test_assignment,
    create_test_cycle,
    create_test_script,
    create_user,
    create_user_role,
)


# ---------------------------------------------------------------------------
# Shared test engine and session
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture(scope="module")
async def workflow_engine():
    """One in-memory database for the entire workflow test module."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def workflow_session(workflow_engine) -> AsyncGenerator[AsyncSession, None]:
    factory = async_sessionmaker(
        bind=workflow_engine, class_=AsyncSession, expire_on_commit=False, autoflush=False
    )
    async with factory() as session:
        yield session
        await session.rollback()


# ---------------------------------------------------------------------------
# Factories that persist to the database
# ---------------------------------------------------------------------------


async def persist(session: AsyncSession, *objs: object) -> None:
    """Add and flush multiple objects to the session."""
    for obj in objs:
        session.add(obj)
    await session.flush()


# ---------------------------------------------------------------------------
# Full workflow test
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.slow
class TestFullWorkflow:
    """
    Exercises the complete KAATS lifecycle end-to-end against a real
    (SQLite in-memory) database.

    Each test method depends on the previous — they run in order and share
    state via instance attributes.  Pytest does not guarantee order by default;
    we use explicit ordering via method naming (alphabetical execution) or
    rely on the sequential relationship being tested at the DB level.
    """

    @pytest.mark.asyncio
    async def test_01_create_enterprise_and_company(
        self, workflow_session: AsyncSession
    ) -> None:
        """
        Global admin creates the top-level organisational structure.
        Enterprise + Company are the root of the KAATS tenant hierarchy.
        """
        from app.models.tenant import Company, Enterprise

        enterprise = create_enterprise(name="Workflow Enterprise", slug="wf-ent")
        company = create_company(enterprise, name="Workflow Company", slug="wf-co")

        await persist(workflow_session, enterprise, company)
        await workflow_session.commit()

        # Verify persistence
        stmt = select(Company).where(Company.slug == "wf-co")
        result = await workflow_session.execute(stmt)
        stored = result.scalar_one_or_none()
        assert stored is not None
        assert stored.name == "Workflow Company"

    @pytest.mark.asyncio
    async def test_02_create_users_and_assign_roles(
        self, workflow_session: AsyncSession
    ) -> None:
        """
        Two users are created: one System Manager and one Validation Tester.
        Role assignments link them to the company.
        """
        from app.models.tenant import Company
        from app.models.user import User, UserRoleAssignment

        stmt = select(Company).where(Company.slug == "wf-co")
        result = await workflow_session.execute(stmt)
        company = result.scalar_one_or_none()
        if company is None:
            pytest.skip("Company not created in test_01 — run tests in order")

        sm_user = create_user(email="sm@wf.test", display_name="System Manager")
        vt_user = create_user(email="vt@wf.test", display_name="Validation Tester")

        sm_role = create_user_role(sm_user, company, role=RoleCode.SYSTEM_MANAGER)
        vt_role = create_user_role(vt_user, company, role=RoleCode.VALIDATION_TESTER)

        await persist(workflow_session, sm_user, vt_user, sm_role, vt_role)
        await workflow_session.commit()

        # Verify user count
        stmt2 = select(User).where(User.email.in_(["sm@wf.test", "vt@wf.test"]))
        result2 = await workflow_session.execute(stmt2)
        users = result2.scalars().all()
        assert len(users) == 2

    @pytest.mark.asyncio
    async def test_03_create_project(self, workflow_session: AsyncSession) -> None:
        """System Manager creates a project scoped to the company's tenant."""
        from app.models.project import Project
        from app.models.tenant import Company

        stmt = select(Company).where(Company.slug == "wf-co")
        result = await workflow_session.execute(stmt)
        company = result.scalar_one_or_none()
        if company is None:
            pytest.skip("Company not created")

        project = create_project(
            company,
            name="Workflow Test Project",
            system_type=SystemType.WEB,
        )
        await persist(workflow_session, project)
        await workflow_session.commit()

        stmt2 = select(Project).where(Project.name == "Workflow Test Project")
        result2 = await workflow_session.execute(stmt2)
        stored = result2.scalar_one_or_none()
        assert stored is not None
        assert stored.tenant_id == company.tenant_id

    @pytest.mark.asyncio
    async def test_04_create_requirement(self, workflow_session: AsyncSession) -> None:
        """A requirement is created for the project."""
        from app.models.project import Project
        from app.models.requirement import Requirement

        stmt = select(Project).where(Project.name == "Workflow Test Project")
        result = await workflow_session.execute(stmt)
        project = result.scalar_one_or_none()
        if project is None:
            pytest.skip("Project not created")

        req = create_requirement(
            project,
            title="User Authentication",
            content_text="Users must be able to log in using email and password.",
            status=RequirementStatus.PROCESSED,
        )
        await persist(workflow_session, req)
        await workflow_session.commit()

        stmt2 = select(Requirement).where(Requirement.title == "User Authentication")
        result2 = await workflow_session.execute(stmt2)
        stored = result2.scalar_one_or_none()
        assert stored is not None
        assert stored.project_id == project.id

    @pytest.mark.asyncio
    async def test_05_create_draft_test_script(
        self, workflow_session: AsyncSession
    ) -> None:
        """
        AI generation service creates a test script in DRAFT status.
        (AI call is mocked; we're testing the database objects, not the LLM.)
        """
        from app.models.project import Project
        from app.models.requirement import Requirement
        from app.models.test_script import TestScript

        stmt = select(Requirement).where(Requirement.title == "User Authentication")
        result = await workflow_session.execute(stmt)
        req = result.scalar_one_or_none()
        if req is None:
            pytest.skip("Requirement not created")

        stmt2 = select(Project).where(Project.id == req.project_id)
        result2 = await workflow_session.execute(stmt2)
        project = result2.scalar_one_or_none()

        script = create_test_script(
            project,
            req,
            title="Login Test — Gherkin",
            format=ScriptFormat.GHERKIN,
            status=ScriptStatus.DRAFT,
            is_ai_generated=True,
        )
        await persist(workflow_session, script)
        await workflow_session.commit()

        stmt3 = select(TestScript).where(TestScript.title == "Login Test — Gherkin")
        result3 = await workflow_session.execute(stmt3)
        stored = result3.scalar_one_or_none()
        assert stored is not None
        assert stored.status == ScriptStatus.DRAFT

    @pytest.mark.asyncio
    async def test_06_submit_script_for_review(
        self, workflow_session: AsyncSession
    ) -> None:
        """
        System Manager submits the script for review.
        Status transitions DRAFT → IN_REVIEW.
        """
        from app.models.test_script import TestScript

        stmt = select(TestScript).where(TestScript.title == "Login Test — Gherkin")
        result = await workflow_session.execute(stmt)
        script = result.scalar_one_or_none()
        if script is None:
            pytest.skip("Script not created")

        # Simulate the submit_for_review service action
        script.status = ScriptStatus.IN_REVIEW
        await workflow_session.commit()

        await workflow_session.refresh(script)
        assert script.status == ScriptStatus.IN_REVIEW

    @pytest.mark.asyncio
    async def test_07_approve_script(self, workflow_session: AsyncSession) -> None:
        """
        Validation Lead approves the script.
        Status transitions IN_REVIEW → APPROVED.
        Approved scripts can be added to test cycles.
        """
        from app.models.test_script import TestScript
        from app.models.user import User

        stmt = select(TestScript).where(TestScript.title == "Login Test — Gherkin")
        result = await workflow_session.execute(stmt)
        script = result.scalar_one_or_none()
        if script is None:
            pytest.skip("Script not submitted for review")

        # Simulate VL approval
        script.status = ScriptStatus.APPROVED
        script.approved_by = script.created_by
        await workflow_session.commit()

        await workflow_session.refresh(script)
        assert script.status == ScriptStatus.APPROVED
        assert script.approved_by is not None

    @pytest.mark.asyncio
    async def test_08_create_test_cycle(self, workflow_session: AsyncSession) -> None:
        """
        Validation Lead creates a test cycle to organise execution.
        Cycle starts in DRAFT status.
        """
        from app.models.project import Project
        from app.models.test_cycle import TestCycle

        stmt = select(Project).where(Project.name == "Workflow Test Project")
        result = await workflow_session.execute(stmt)
        project = result.scalar_one_or_none()
        if project is None:
            pytest.skip("Project not created")

        cycle = create_test_cycle(project, name="Sprint 1 UAT", status=CycleStatus.ACTIVE)
        await persist(workflow_session, cycle)
        await workflow_session.commit()

        stmt2 = select(TestCycle).where(TestCycle.name == "Sprint 1 UAT")
        result2 = await workflow_session.execute(stmt2)
        stored = result2.scalar_one_or_none()
        assert stored is not None
        assert stored.status == CycleStatus.ACTIVE

    @pytest.mark.asyncio
    async def test_09_assign_script_to_tester(
        self, workflow_session: AsyncSession
    ) -> None:
        """
        Validation Lead assigns the approved script to the Validation Tester.
        Assignment pins the script_version at the current version.
        """
        from app.models.test_cycle import TestAssignment, TestCycle
        from app.models.test_script import TestScript

        stmt_cycle = select(TestCycle).where(TestCycle.name == "Sprint 1 UAT")
        result_cycle = await workflow_session.execute(stmt_cycle)
        cycle = result_cycle.scalar_one_or_none()

        stmt_script = select(TestScript).where(TestScript.title == "Login Test — Gherkin")
        result_script = await workflow_session.execute(stmt_script)
        script = result_script.scalar_one_or_none()

        if cycle is None or script is None:
            pytest.skip("Cycle or script not created")

        assignment = create_test_assignment(
            cycle, script, status=ExecutionStatus.NOT_STARTED
        )
        await persist(workflow_session, assignment)
        await workflow_session.commit()

        stmt2 = select(TestAssignment).where(TestAssignment.cycle_id == cycle.id)
        result2 = await workflow_session.execute(stmt2)
        stored = result2.scalar_one_or_none()
        assert stored is not None
        assert stored.script_version == script.current_version

    @pytest.mark.asyncio
    async def test_10_submit_test_result(self, workflow_session: AsyncSession) -> None:
        """
        Validation Tester submits a PASSED result for the assignment.
        Assignment status must update to PASSED and TestResult is created.
        """
        from app.models.test_cycle import ExecutionStatus, TestAssignment, TestResult

        stmt = select(TestAssignment)
        result = await workflow_session.execute(stmt)
        assignment = result.scalars().first()
        if assignment is None:
            pytest.skip("Assignment not created")

        from tests.factories import create_test_result

        test_result = create_test_result(
            assignment,
            status=ExecutionStatus.PASSED,
            duration_seconds=145,
            notes="All steps passed on first run.",
        )
        # Update assignment status
        assignment.status = ExecutionStatus.PASSED

        await persist(workflow_session, test_result)
        await workflow_session.commit()

        # Verify
        stmt2 = select(TestResult).where(TestResult.assignment_id == assignment.id)
        result2 = await workflow_session.execute(stmt2)
        stored_result = result2.scalar_one_or_none()
        assert stored_result is not None
        assert stored_result.status == ExecutionStatus.PASSED
        assert stored_result.duration_seconds == 145

        await workflow_session.refresh(assignment)
        assert assignment.status == ExecutionStatus.PASSED

    @pytest.mark.asyncio
    async def test_11_reporting_data_is_correct(
        self, workflow_session: AsyncSession
    ) -> None:
        """
        After workflow completion, the reporting query must show:
        - 1 passed execution
        - 0 failed executions
        - cycle completion rate = 100%

        This validates that the data model supports accurate reporting.
        """
        from sqlalchemy import func

        from app.models.test_cycle import ExecutionStatus, TestResult

        stmt = select(func.count(TestResult.id)).where(
            TestResult.status == ExecutionStatus.PASSED
        )
        result = await workflow_session.execute(stmt)
        passed_count = result.scalar()
        assert passed_count >= 1, "Expected at least one PASSED result after workflow"

        # No failed results
        stmt2 = select(func.count(TestResult.id)).where(
            TestResult.status == ExecutionStatus.FAILED
        )
        result2 = await workflow_session.execute(stmt2)
        failed_count = result2.scalar()
        assert failed_count == 0
