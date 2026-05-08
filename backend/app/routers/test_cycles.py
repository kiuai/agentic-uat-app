"""Test cycle and execution endpoints."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, File, Query, UploadFile, status

from app.auth.permissions import Permission
from app.dependencies import CurrentUser, CosmosDep, RequirePermission, TenantDB
from app.exporters.base import ExportFormat
from app.models.test_script import ScriptFormat
from app.schemas.test_cycle import (
    EvidenceRead,
    ExecutionCreate,
    ExecutionRead,
    ExecutionUpdate,
    TestCycleCreate,
    TestCycleRead,
    TestCycleUpdate,
)
from app.schemas.test_script import BulkExportResponse
from app.services.export_service import ExportService
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


# ── Cycle-level export (no project_id needed in path) ─────────────────────────

cycle_export_router = APIRouter(prefix="/test-cycles")


@cycle_export_router.get(
    "/{cycle_id}/export",
    response_model=BulkExportResponse,
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[
        Depends(RequirePermission(Permission.SCRIPT_EXPORT)),
        Depends(RequirePermission(Permission.CYCLE_READ)),
    ],
    summary="Export all approved scripts in a test cycle as a ZIP archive",
)
async def export_cycle(
    cycle_id: uuid.UUID,
    db: TenantDB,
    cosmos: CosmosDep,
    current_user: CurrentUser,
    format: ScriptFormat = Query(..., description="Target export format"),
    project_name: str = Query("KAATS", description="Project name for generated file headers"),
    system_url: str = Query("", description="Base URL of the system under test"),
) -> BulkExportResponse:
    svc = ExportService(db, cosmos)
    result = await svc.export_test_cycle(
        test_cycle_id=cycle_id,
        export_format=ExportFormat(format.value),
        tenant_id=current_user.tenant_id,
        project_name=project_name,
        system_url=system_url,
    )
    return BulkExportResponse(
        format=format,
        blob_uri=result.blob_uri,
        download_url=result.download_url,
        expires_at=result.expires_at,
        file_count=result.file_count,
        generated_at=result.generated_at,
    )
