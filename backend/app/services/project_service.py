"""Project and Environment service."""

from __future__ import annotations

import uuid

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.project import Environment, Project, ProjectStatus
from app.models.test_cycle import CycleStatus, Execution, ExecutionStatus, TestCycle
from app.schemas.project import (
    EnvironmentCreate, EnvironmentRead, EnvironmentUpdate,
    ProjectCreate, ProjectRead, ProjectUpdate,
)
from app.routers.reports import ProjectSummaryReport


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
        if body.name is not None:
            project.name = body.name
        if body.description is not None:
            project.description = body.description
        if body.status is not None:
            project.status = body.status
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

    async def get_summary_report(
        self, project_id: uuid.UUID, tenant_id: uuid.UUID
    ) -> ProjectSummaryReport:
        cycles_result = await self._db.execute(
            select(func.count(TestCycle.id), func.count()).where(
                TestCycle.project_id == project_id,
                TestCycle.tenant_id == tenant_id,
            )
        )
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

        exec_counts: dict[str, int] = {}
        for exec_status in ExecutionStatus:
            count = await self._db.scalar(
                select(func.count(Execution.id)).where(
                    Execution.cycle_id.in_(cycle_ids),
                    Execution.status == exec_status,
                )
            ) or 0
            exec_counts[exec_status.value] = count

        total_exec = sum(exec_counts.values())
        passed = exec_counts.get("PASSED", 0)
        pass_rate = round(passed / total_exec * 100, 1) if total_exec else 0.0

        return ProjectSummaryReport(
            project_id=project_id,
            total_scripts=0,
            approved_scripts=0,
            total_cycles=total_cycles,
            active_cycles=active_cycles,
            total_executions=total_exec,
            passed=passed,
            failed=exec_counts.get("FAILED", 0),
            blocked=exec_counts.get("BLOCKED", 0),
            not_started=exec_counts.get("NOT_STARTED", 0),
            pass_rate=pass_rate,
        )
