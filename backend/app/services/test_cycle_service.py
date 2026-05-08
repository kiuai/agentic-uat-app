"""Test cycle and execution service."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import structlog
from fastapi import HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.middleware.rbac import assert_assigned_execution
from app.models.test_cycle import (
    CycleStatus,
    ExecutionEvidence,
    ExecutionStatus,
    TestAssignment,
    TestCycle,
    TestResult,
)
from app.schemas.test_cycle import (
    EvidenceRead,
    ExecutionCreate,
    ExecutionRead,
    ExecutionUpdate,
    TestAssignmentCreate,
    TestAssignmentResponse,
    TestAssignmentUpdate,
    TestCycleCreate,
    TestCycleRead,
    TestCycleUpdate,
    TestResultCreate,
    TestResultResponse,
)

logger = structlog.get_logger(__name__)


class TestCycleService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    # ── Cycles ────────────────────────────────────────────────────────────────

    async def list_cycles(
        self, project_id: uuid.UUID, tenant_id: uuid.UUID
    ) -> list[TestCycleRead]:
        result = await self._db.execute(
            select(TestCycle)
            .where(
                TestCycle.project_id == project_id,
                TestCycle.tenant_id == tenant_id,
            )
            .order_by(TestCycle.created_at.desc())
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
            description=body.description,
            created_by=user_id,
            lead_user_id=body.lead_user_id,
            planned_start_date=body.planned_start_date,
            planned_end_date=body.planned_end_date,
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

    # ── Assignments (formerly "Executions") ───────────────────────────────────

    async def list_executions(self, cycle_id: uuid.UUID) -> list[TestAssignmentResponse]:
        result = await self._db.execute(
            select(TestAssignment)
            .where(TestAssignment.cycle_id == cycle_id)
            .order_by(TestAssignment.created_at)
        )
        return [TestAssignmentResponse.model_validate(a) for a in result.scalars()]

    async def add_execution(
        self, cycle_id: uuid.UUID, tenant_id: uuid.UUID, user_id: uuid.UUID, body: ExecutionCreate
    ) -> TestAssignmentResponse:
        assignment = TestAssignment(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            cycle_id=cycle_id,
            script_id=body.script_id,
            script_version=body.script_version,
            assigned_to=body.assigned_to,
            assigned_by=user_id,
            due_date=body.due_date,
            notes=body.notes,
            status=ExecutionStatus.NOT_STARTED,
        )
        self._db.add(assignment)
        await self._db.flush()
        await self._db.refresh(assignment)
        return TestAssignmentResponse.model_validate(assignment)

    async def bulk_assign(
        self,
        cycle_id: uuid.UUID,
        tenant_id: uuid.UUID,
        user_id: uuid.UUID,
        assignments: list[TestAssignmentCreate],
    ) -> list[TestAssignmentResponse]:
        created = []
        for body in assignments:
            result = await self.add_execution(cycle_id, tenant_id, user_id, body)
            created.append(result)
        return created

    async def update_assignment(
        self,
        assignment_id: uuid.UUID,
        user_roles: list,
        requester_id: uuid.UUID,
        body: TestAssignmentUpdate,
    ) -> TestAssignmentResponse:
        assignment = await self._db.get(TestAssignment, assignment_id)
        if not assignment:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assignment not found.")
        assert_assigned_execution(user_roles, requester_id, assignment.assigned_to)
        for field, value in body.model_dump(exclude_none=True).items():
            setattr(assignment, field, value)
        await self._db.flush()
        await self._db.refresh(assignment)
        return TestAssignmentResponse.model_validate(assignment)

    async def submit_result(
        self,
        assignment_id: uuid.UUID,
        user_roles: list,
        requester_id: uuid.UUID,
        tenant_id: uuid.UUID,
        body: TestResultCreate,
    ) -> TestResultResponse:
        assignment = await self._db.get(TestAssignment, assignment_id)
        if not assignment:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assignment not found.")
        assert_assigned_execution(user_roles, requester_id, assignment.assigned_to)

        # Update assignment status to match result
        assignment.status = body.status

        # Check for existing result (idempotent re-submission)
        existing = await self._db.scalar(
            select(TestResult).where(TestResult.assignment_id == assignment_id)
        )
        if existing:
            existing.status = body.status
            existing.executed_at = body.executed_at
            existing.duration_seconds = body.duration_seconds
            existing.notes = body.notes
            if body.step_results:
                import json
                existing.step_results = json.dumps(body.step_results)
            await self._db.flush()
            await self._db.refresh(existing)
            return TestResultResponse.model_validate(existing)

        import json
        result = TestResult(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            assignment_id=assignment_id,
            status=body.status,
            executed_by=requester_id,
            executed_at=body.executed_at,
            duration_seconds=body.duration_seconds,
            notes=body.notes,
            step_results=json.dumps(body.step_results) if body.step_results else None,
        )
        self._db.add(result)
        await self._db.flush()
        await self._db.refresh(result)
        return TestResultResponse.model_validate(result)

    # Legacy alias used by existing router
    async def log_result(
        self,
        exec_id: uuid.UUID,
        user_roles: list,
        requester_id: uuid.UUID,
        tenant_id: uuid.UUID,
        body: ExecutionUpdate,
    ) -> TestAssignmentResponse:
        assignment = await self._db.get(TestAssignment, exec_id)
        if not assignment:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assignment not found.")
        assert_assigned_execution(user_roles, requester_id, assignment.assigned_to)
        for field, value in body.model_dump(exclude_none=True).items():
            setattr(assignment, field, value)
        await self._db.flush()
        await self._db.refresh(assignment)
        return TestAssignmentResponse.model_validate(assignment)

    # ── Evidence ──────────────────────────────────────────────────────────────

    async def upload_evidence(
        self,
        assignment_id: uuid.UUID,
        user_roles: list,
        requester_id: uuid.UUID,
        tenant_id: uuid.UUID,
        file: UploadFile,
    ) -> EvidenceRead:
        assignment = await self._db.get(TestAssignment, assignment_id)
        if not assignment:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assignment not found.")
        assert_assigned_execution(user_roles, requester_id, assignment.assigned_to)

        test_result = await self._db.scalar(
            select(TestResult).where(TestResult.assignment_id == assignment_id)
        )
        if not test_result:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Submit a test result before uploading evidence.",
            )

        from app.services.blob_service import BlobService
        blob_service = BlobService()
        blob_path = f"evidence/{assignment_id}/{file.filename}"
        content = await file.read()
        blob_uri = await blob_service.upload(
            tenant_id, blob_path, content, file.content_type or "application/octet-stream"
        )

        evidence = ExecutionEvidence(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            result_id=test_result.id,
            blob_uri=blob_uri,
            file_name=file.filename or "evidence",
            content_type=file.content_type,
            uploaded_by=requester_id,
            uploaded_at=datetime.now(timezone.utc),
        )
        self._db.add(evidence)
        await self._db.flush()
        await self._db.refresh(evidence)
        return EvidenceRead.model_validate(evidence)
