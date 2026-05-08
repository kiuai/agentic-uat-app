"""Test cycle and execution endpoints."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, File, UploadFile, status

from app.auth.permissions import Permission
from app.dependencies import CurrentUser, RequirePermission, TenantDB
from app.schemas.test_cycle import (
    EvidenceRead,
    ExecutionCreate,
    ExecutionRead,
    ExecutionUpdate,
    TestCycleCreate,
    TestCycleRead,
    TestCycleUpdate,
)
from app.services.test_cycle_service import TestCycleService

router = APIRouter(prefix="/projects/{project_id}/cycles")


@router.get(
    "",
    response_model=list[TestCycleRead],
    dependencies=[Depends(RequirePermission(Permission.CYCLE_READ))],
)
async def list_cycles(
    project_id: uuid.UUID, db: TenantDB, current_user: CurrentUser
) -> list[TestCycleRead]:
    service = TestCycleService(db)
    return await service.list_cycles(project_id, current_user.tenant_id)


@router.post(
    "",
    response_model=TestCycleRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(RequirePermission(Permission.CYCLE_CREATE))],
)
async def create_cycle(
    project_id: uuid.UUID, body: TestCycleCreate, db: TenantDB, current_user: CurrentUser
) -> TestCycleRead:
    service = TestCycleService(db)
    return await service.create_cycle(project_id, current_user.tenant_id, current_user.id, body)


@router.get(
    "/{cycle_id}",
    response_model=TestCycleRead,
    dependencies=[Depends(RequirePermission(Permission.CYCLE_READ))],
)
async def get_cycle(project_id: uuid.UUID, cycle_id: uuid.UUID, db: TenantDB) -> TestCycleRead:
    service = TestCycleService(db)
    return await service.get_cycle(cycle_id)


@router.patch(
    "/{cycle_id}",
    response_model=TestCycleRead,
    dependencies=[Depends(RequirePermission(Permission.CYCLE_UPDATE))],
)
async def update_cycle(
    project_id: uuid.UUID, cycle_id: uuid.UUID, body: TestCycleUpdate, db: TenantDB
) -> TestCycleRead:
    service = TestCycleService(db)
    return await service.update_cycle(cycle_id, body)


@router.post(
    "/{cycle_id}/activate",
    response_model=TestCycleRead,
    dependencies=[Depends(RequirePermission(Permission.CYCLE_UPDATE))],
)
async def activate_cycle(
    project_id: uuid.UUID, cycle_id: uuid.UUID, db: TenantDB
) -> TestCycleRead:
    service = TestCycleService(db)
    return await service.activate_cycle(cycle_id)


@router.post(
    "/{cycle_id}/close",
    response_model=TestCycleRead,
    dependencies=[Depends(RequirePermission(Permission.CYCLE_UPDATE))],
)
async def close_cycle(
    project_id: uuid.UUID, cycle_id: uuid.UUID, db: TenantDB
) -> TestCycleRead:
    service = TestCycleService(db)
    return await service.close_cycle(cycle_id)


# ── Executions ────────────────────────────────────────────────────────────────

@router.get(
    "/{cycle_id}/executions",
    response_model=list[ExecutionRead],
    dependencies=[Depends(RequirePermission(Permission.CYCLE_READ))],
)
async def list_executions(
    project_id: uuid.UUID, cycle_id: uuid.UUID, db: TenantDB
) -> list[ExecutionRead]:
    service = TestCycleService(db)
    return await service.list_executions(cycle_id)


@router.post(
    "/{cycle_id}/executions",
    response_model=ExecutionRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(RequirePermission(Permission.CYCLE_UPDATE))],
)
async def add_execution(
    project_id: uuid.UUID,
    cycle_id: uuid.UUID,
    body: ExecutionCreate,
    db: TenantDB,
    current_user: CurrentUser,
) -> ExecutionRead:
    service = TestCycleService(db)
    return await service.add_execution(cycle_id, current_user.tenant_id, body)


@router.patch(
    "/{cycle_id}/executions/{exec_id}",
    response_model=ExecutionRead,
    dependencies=[Depends(RequirePermission(Permission.EXECUTION_LOG))],
)
async def log_execution_result(
    project_id: uuid.UUID,
    cycle_id: uuid.UUID,
    exec_id: uuid.UUID,
    body: ExecutionUpdate,
    db: TenantDB,
    current_user: CurrentUser,
) -> ExecutionRead:
    service = TestCycleService(db)
    return await service.log_result(exec_id, current_user, body)


@router.post(
    "/{cycle_id}/executions/{exec_id}/evidence",
    response_model=EvidenceRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(RequirePermission(Permission.EXECUTION_EVIDENCE_UPLOAD))],
)
async def upload_evidence(
    project_id: uuid.UUID,
    cycle_id: uuid.UUID,
    exec_id: uuid.UUID,
    file: UploadFile = File(...),
    db: TenantDB = Depends(),
    current_user: CurrentUser = Depends(),
) -> EvidenceRead:
    service = TestCycleService(db)
    return await service.upload_evidence(exec_id, current_user, file)
