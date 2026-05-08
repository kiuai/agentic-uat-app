"""Test cycle and execution service."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import structlog

from app.middleware.rbac import assert_assigned_execution
from app.models.test_cycle import (
    CycleStatus, Execution, ExecutionEvidence, ExecutionStatus, TestCycle
)
from app.models.user import User
from app.schemas.test_cycle import (
    EvidenceRead, ExecutionCreate, ExecutionRead, ExecutionUpdate,
    TestCycleCreate, TestCycleRead, TestCycleUpdate,
)

logger = structlog.get_logger(__name__)


class TestCycleService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def list_cycles(
        self, project_id: uuid.UUID, tenant_id: uuid.UUID
    ) -> list[TestCycleRead]:
        result = await self._db.execute(
            select(TestCycle).where(
                TestCycle.project_id == project_id,
                TestCycle.tenant_id == tenant_id,
            ).order_by(TestCycle.created_at.desc())
        )
        return [TestCycleRead.model_validate(c) for c in result.scalars()]

    async def create_cycle(
        self,
        project_id: uuid.UUID,
        tenant_id: uuid.UUID,
        user_id: uuid.UUID,
        body: TestCycleCreate,
    ) -> TestCycleRead:
        cycle = TestCycle(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            project_id=project_id,
            environment_id=body.environment_id,
            name=body.name,
            created_by=user_id,
            start_date=body.start_date,
            end_date=body.end_date,
        )
        self._db.add(cycle)
        await self._db.flush()
        await self._db.refresh(cycle)
        return TestCycleRead.model_validate(cycle)

    async def get_cycle(self, cycle_id: uuid.UUID) -> TestCycleRead:
        cycle = await self._db.get(TestCycle, cycle_id)
        if not cycle:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cycle not found.")
        return TestCycleRead.model_validate(cycle)

    async def update_cycle(
        self, cycle_id: uuid.UUID, body: TestCycleUpdate
    ) -> TestCycleRead:
        cycle = await self._db.get(TestCycle, cycle_id)
        if not cycle:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cycle not found.")
        if cycle.status == CycleStatus.LOCKED:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="LOCKED cycles cannot be modified.",
            )
        for field, value in body.model_dump(exclude_none=True).items():
            setattr(cycle, field, value)
        await self._db.flush()
        await self._db.refresh(cycle)
        return TestCycleRead.model_validate(cycle)

    async def activate_cycle(self, cycle_id: uuid.UUID) -> TestCycleRead:
        cycle = await self._db.get(TestCycle, cycle_id)
        if not cycle:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cycle not found.")
        if cycle.status != CycleStatus.DRAFT:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Only DRAFT cycles can be activated. Current: {cycle.status.value}",
            )
        cycle.status = CycleStatus.ACTIVE
        await self._db.flush()
        await self._db.refresh(cycle)
        return TestCycleRead.model_validate(cycle)

    async def close_cycle(self, cycle_id: uuid.UUID) -> TestCycleRead:
        cycle = await self._db.get(TestCycle, cycle_id)
        if not cycle:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cycle not found.")
        cycle.status = CycleStatus.LOCKED
        await self._db.flush()
        await self._db.refresh(cycle)
        return TestCycleRead.model_validate(cycle)

    async def list_executions(self, cycle_id: uuid.UUID) -> list[ExecutionRead]:
        result = await self._db.execute(
            select(Execution).where(Execution.cycle_id == cycle_id)
        )
        return [ExecutionRead.model_validate(e) for e in result.scalars()]

    async def add_execution(
        self, cycle_id: uuid.UUID, tenant_id: uuid.UUID, body: ExecutionCreate
    ) -> ExecutionRead:
        execution = Execution(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            cycle_id=cycle_id,
            cosmos_script_id=body.cosmos_script_id,
            script_version=body.script_version,
            assigned_to=body.assigned_to,
        )
        self._db.add(execution)
        await self._db.flush()
        await self._db.refresh(execution)
        return ExecutionRead.model_validate(execution)

    async def log_result(
        self, exec_id: uuid.UUID, user: User, body: ExecutionUpdate
    ) -> ExecutionRead:
        execution = await self._db.get(Execution, exec_id)
        if not execution:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Execution not found.")

        assert_assigned_execution(user, execution.assigned_to)

        if body.status is not None:
            execution.status = body.status
        if body.notes is not None:
            execution.notes = body.notes
        if body.executed_at is not None:
            execution.executed_at = body.executed_at
        execution.executed_by = user.id

        await self._db.flush()
        await self._db.refresh(execution)
        return ExecutionRead.model_validate(execution)

    async def upload_evidence(
        self, exec_id: uuid.UUID, user: User, file: UploadFile
    ) -> EvidenceRead:
        execution = await self._db.get(Execution, exec_id)
        if not execution:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Execution not found.")

        assert_assigned_execution(user, execution.assigned_to)

        from app.services.blob_service import BlobService
        blob_service = BlobService()
        blob_path = f"evidence/{exec_id}/{file.filename}"
        content = await file.read()
        blob_uri = await blob_service.upload(
            user.tenant_id, blob_path, content, file.content_type or "application/octet-stream"
        )

        evidence = ExecutionEvidence(
            id=uuid.uuid4(),
            tenant_id=user.tenant_id,
            execution_id=exec_id,
            blob_uri=blob_uri,
            file_name=file.filename or "evidence",
            uploaded_by=user.id,
            uploaded_at=datetime.now(timezone.utc),
        )
        self._db.add(evidence)
        await self._db.flush()
        await self._db.refresh(evidence)
        return EvidenceRead.model_validate(evidence)
