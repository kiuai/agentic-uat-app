"""Project and Environment service."""

from __future__ import annotations

import uuid

from fastapi import HTTPException, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.project import Environment, Project, ProjectStatus
from app.models.test_cycle import CycleStatus, ExecutionStatus, TestAssignment, TestCycle, TestResult
from app.models.test_script import ScriptStatus, TestScript
from app.schemas.project import (
    EnvironmentCreate,
    EnvironmentRead,
    EnvironmentUpdate,
    ProjectCreate,
    ProjectRead,
    ProjectUpdate,
)


# ---------------------------------------------------------------------------
# Report schema (defined here to avoid circular import with reports router)
# ---------------------------------------------------------------------------


class ProjectSummaryReport(BaseModel):
    project_id: uuid.UUID
    total_scripts: int
    approved_scripts: int
    total_requirements: int
    total_cycles: int
    active_cycles: int
    total_assignments: int
    passed: int
    failed: int
    blocked: int
    not_started: int
    pass_rate: float


class ProjectDashboard(BaseModel):
    project_id: uuid.UUID
    name: str
    total_requirements: int
    pending_requirements: int
    total_scripts: int
    draft_scripts: int
    approved_scripts: int
    total_cycles: int
    active_cycles: int
    total_assignments: int
    pass_rate: float


class ProjectService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def list_projects(self, tenant_id: uuid.UUID) -> list[ProjectRead]:
        result = await self._db.execute(
            select(Project).where(
                Project.tenant_id == tenant_id,
                Project.status == ProjectStatus.ACTIVE,
            )
        )
        return [ProjectRead.model_validate(p) for p in result.scalars()]

    async def create_project(
        self, tenant_id: uuid.UUID, created_by: uuid.UUID, body: ProjectCreate
    ) -> ProjectRead:
        project = Project(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            name=body.name,
            description=body.description,
            system_type=body.system_type,
            base_url=body.base_url,
            settings=body.settings,
            created_by=created_by,
        )
        self._db.add(project)
        await self._db.flush()
        await self._db.refresh(project)
        return ProjectRead.model_validate(project)

    async def get_project(self, project_id: uuid.UUID) -> ProjectRead:
        project = await self._db.get(Project, project_id)
        if not project:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found.")
        return ProjectRead.model_validate(project)

    async def update_project(self, project_id: uuid.UUID, body: ProjectUpdate) -> ProjectRead:
        project = await self._db.get(Project, project_id)
        if not project:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found.")
        for field, value in body.model_dump(exclude_none=True).items():
            setattr(project, field, value)
        await self._db.flush()
        await self._db.refresh(project)
        return ProjectRead.model_validate(project)

    async def archive_project(self, project_id: uuid.UUID) -> None:
        project = await self._db.get(Project, project_id)
        if not project:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found.")
        project.status = ProjectStatus.ARCHIVED
        await self._db.flush()

    async def list_environments(
        self, project_id: uuid.UUID, tenant_id: uuid.UUID
    ) -> list[EnvironmentRead]:
        result = await self._db.execute(
            select(Environment).where(
                Environment.project_id == project_id,
                Environment.tenant_id == tenant_id,
            )
        )
        return [EnvironmentRead.model_validate(e) for e in result.scalars()]

    async def create_environment(
        self, project_id: uuid.UUID, tenant_id: uuid.UUID, body: EnvironmentCreate
    ) -> EnvironmentRead:
        env = Environment(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            project_id=project_id,
            name=body.name,
            type=body.type,
            base_url=body.base_url,
            requires_bpo_approval=body.requires_bpo_approval,
            gxp_mode=body.gxp_mode,
        )
        self._db.add(env)
        await self._db.flush()
        await self._db.refresh(env)
        return EnvironmentRead.model_validate(env)

    async def update_environment(
        self, env_id: uuid.UUID, body: EnvironmentUpdate
    ) -> EnvironmentRead:
        env = await self._db.get(Environment, env_id)
        if not env:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Environment not found.")
        for field, value in body.model_dump(exclude_none=True).items():
            setattr(env, field, value)
        await self._db.flush()
        await self._db.refresh(env)
        return EnvironmentRead.model_validate(env)

    async def delete_environment(self, env_id: uuid.UUID) -> None:
        env = await self._db.get(Environment, env_id)
        if not env:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Environment not found.")
        await self._db.delete(env)
        await self._db.flush()

    async def get_dashboard(
        self, project_id: uuid.UUID, tenant_id: uuid.UUID
    ) -> ProjectDashboard:
        from app.models.requirement import Requirement, RequirementStatus

        project = await self._db.get(Project, project_id)
        if not project:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found.")

        total_reqs = await self._db.scalar(
            select(func.count(Requirement.id)).where(
                Requirement.project_id == project_id, Requirement.tenant_id == tenant_id
            )
        ) or 0
        pending_reqs = await self._db.scalar(
            select(func.count(Requirement.id)).where(
                Requirement.project_id == project_id,
                Requirement.tenant_id == tenant_id,
                Requirement.status == RequirementStatus.PENDING,
            )
        ) or 0
        total_scripts = await self._db.scalar(
            select(func.count(TestScript.id)).where(
                TestScript.project_id == project_id, TestScript.tenant_id == tenant_id
            )
        ) or 0
        draft_scripts = await self._db.scalar(
            select(func.count(TestScript.id)).where(
                TestScript.project_id == project_id,
                TestScript.tenant_id == tenant_id,
                TestScript.status == ScriptStatus.DRAFT,
            )
        ) or 0
        approved_scripts = await self._db.scalar(
            select(func.count(TestScript.id)).where(
                TestScript.project_id == project_id,
                TestScript.tenant_id == tenant_id,
                TestScript.status == ScriptStatus.APPROVED,
            )
        ) or 0
        total_cycles = await self._db.scalar(
            select(func.count(TestCycle.id)).where(
                TestCycle.project_id == project_id, TestCycle.tenant_id == tenant_id
            )
        ) or 0
        active_cycles = await self._db.scalar(
            select(func.count(TestCycle.id)).where(
                TestCycle.project_id == project_id,
                TestCycle.tenant_id == tenant_id,
                TestCycle.status == CycleStatus.ACTIVE,
            )
        ) or 0

        # Assignment stats via cycle IDs
        cycle_ids_result = await self._db.execute(
            select(TestCycle.id).where(
                TestCycle.project_id == project_id, TestCycle.tenant_id == tenant_id
            )
        )
        cycle_ids = [r[0] for r in cycle_ids_result]

        total_assignments = 0
        passed = 0
        if cycle_ids:
            total_assignments = await self._db.scalar(
                select(func.count(TestAssignment.id)).where(
                    TestAssignment.cycle_id.in_(cycle_ids)
                )
            ) or 0
            passed = await self._db.scalar(
                select(func.count(TestAssignment.id)).where(
                    TestAssignment.cycle_id.in_(cycle_ids),
                    TestAssignment.status == ExecutionStatus.PASSED,
                )
            ) or 0

        pass_rate = round(passed / total_assignments * 100, 1) if total_assignments else 0.0

        return ProjectDashboard(
            project_id=project_id,
            name=project.name,
            total_requirements=total_reqs,
            pending_requirements=pending_reqs,
            total_scripts=total_scripts,
            draft_scripts=draft_scripts,
            approved_scripts=approved_scripts,
            total_cycles=total_cycles,
            active_cycles=active_cycles,
            total_assignments=total_assignments,
            pass_rate=pass_rate,
        )

    async def get_summary_report(
        self, project_id: uuid.UUID, tenant_id: uuid.UUID
    ) -> ProjectSummaryReport:
        from app.models.requirement import Requirement

        total_reqs = await self._db.scalar(
            select(func.count(Requirement.id)).where(
                Requirement.project_id == project_id, Requirement.tenant_id == tenant_id
            )
        ) or 0
        total_scripts = await self._db.scalar(
            select(func.count(TestScript.id)).where(
                TestScript.project_id == project_id, TestScript.tenant_id == tenant_id
            )
        ) or 0
        approved_scripts = await self._db.scalar(
            select(func.count(TestScript.id)).where(
                TestScript.project_id == project_id,
                TestScript.tenant_id == tenant_id,
                TestScript.status == ScriptStatus.APPROVED,
            )
        ) or 0
        total_cycles = await self._db.scalar(
            select(func.count(TestCycle.id)).where(
                TestCycle.project_id == project_id, TestCycle.tenant_id == tenant_id
            )
        ) or 0
        active_cycles = await self._db.scalar(
            select(func.count(TestCycle.id)).where(
                TestCycle.project_id == project_id,
                TestCycle.tenant_id == tenant_id,
                TestCycle.status == CycleStatus.ACTIVE,
            )
        ) or 0

        cycle_ids_result = await self._db.execute(
            select(TestCycle.id).where(
                TestCycle.project_id == project_id, TestCycle.tenant_id == tenant_id
            )
        )
        cycle_ids = [r[0] for r in cycle_ids_result]

        total_assignments = passed = failed = blocked = not_started = 0
        if cycle_ids:
            passed = await self._db.scalar(
                select(func.count(TestAssignment.id)).where(
                    TestAssignment.cycle_id.in_(cycle_ids),
                    TestAssignment.status == ExecutionStatus.PASSED,
                )
            ) or 0
            failed = await self._db.scalar(
                select(func.count(TestAssignment.id)).where(
                    TestAssignment.cycle_id.in_(cycle_ids),
                    TestAssignment.status == ExecutionStatus.FAILED,
                )
            ) or 0
            blocked = await self._db.scalar(
                select(func.count(TestAssignment.id)).where(
                    TestAssignment.cycle_id.in_(cycle_ids),
                    TestAssignment.status == ExecutionStatus.BLOCKED,
                )
            ) or 0
            not_started = await self._db.scalar(
                select(func.count(TestAssignment.id)).where(
                    TestAssignment.cycle_id.in_(cycle_ids),
                    TestAssignment.status == ExecutionStatus.NOT_STARTED,
                )
            ) or 0
            total_assignments = passed + failed + blocked + not_started

        pass_rate = round(passed / total_assignments * 100, 1) if total_assignments else 0.0

        return ProjectSummaryReport(
            project_id=project_id,
            total_scripts=total_scripts,
            approved_scripts=approved_scripts,
            total_requirements=total_reqs,
            total_cycles=total_cycles,
            active_cycles=active_cycles,
            total_assignments=total_assignments,
            passed=passed,
            failed=failed,
            blocked=blocked,
            not_started=not_started,
            pass_rate=pass_rate,
        )
