"""Test script repository endpoints."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query, status

from app.auth.permissions import Permission
from app.dependencies import CurrentUser, CosmosDep, RequirePermission, TenantDB
from app.exporters.base import ExportFormat
from app.models.test_script import ScriptFormat
from app.schemas.test_script import (
    ApprovalRequest,
    BulkExportRequest,
    BulkExportResponse,
    ExportRequest,
    ExportResponse,
    RejectionRequest,
    TestScriptCreate,
    TestScriptRead,
    TestScriptUpdate,
)
from app.services.export_service import ExportService
from app.services.test_script_service import TestScriptService

# ── Project-scoped CRUD router ────────────────────────────────────────────────

router = APIRouter(prefix="/projects/{project_id}/test-scripts")


@router.get(
    "",
    response_model=list[TestScriptRead],
    dependencies=[Depends(RequirePermission(Permission.SCRIPT_READ))],
)
async def list_scripts(
    project_id: uuid.UUID,
    cosmos: CosmosDep,
    current_user: CurrentUser,
    status_filter: str | None = None,
    domain_code: str | None = None,
) -> list[TestScriptRead]:
    service = TestScriptService(cosmos)
    return await service.list_scripts(
        project_id, status_filter=status_filter, domain_code=domain_code, user=current_user
    )


@router.post(
    "",
    response_model=TestScriptRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(RequirePermission(Permission.SCRIPT_CREATE))],
)
async def create_script(
    project_id: uuid.UUID,
    body: TestScriptCreate,
    cosmos: CosmosDep,
    current_user: CurrentUser,
) -> TestScriptRead:
    service = TestScriptService(cosmos)
    return await service.create_script(project_id, current_user.tenant_id, current_user.id, body)


@router.get(
    "/{script_id}",
    response_model=TestScriptRead,
    dependencies=[Depends(RequirePermission(Permission.SCRIPT_READ))],
)
async def get_script(
    project_id: uuid.UUID, script_id: str, cosmos: CosmosDep, current_user: CurrentUser
) -> TestScriptRead:
    service = TestScriptService(cosmos)
    return await service.get_script(script_id, str(project_id), current_user)


@router.patch(
    "/{script_id}",
    response_model=TestScriptRead,
    dependencies=[Depends(RequirePermission(Permission.SCRIPT_UPDATE))],
)
async def update_script(
    project_id: uuid.UUID,
    script_id: str,
    body: TestScriptUpdate,
    cosmos: CosmosDep,
    current_user: CurrentUser,
) -> TestScriptRead:
    service = TestScriptService(cosmos)
    return await service.update_script(script_id, str(project_id), body, current_user)


@router.delete(
    "/{script_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(RequirePermission(Permission.SCRIPT_DELETE))],
)
async def delete_script(
    project_id: uuid.UUID, script_id: str, cosmos: CosmosDep
) -> None:
    service = TestScriptService(cosmos)
    await service.delete_script(script_id, str(project_id))


@router.get(
    "/{script_id}/content",
    response_model=dict[str, str],
    dependencies=[Depends(RequirePermission(Permission.SCRIPT_READ))],
    summary="Return all script bodies keyed by format",
)
async def get_script_content(
    project_id: uuid.UUID,
    script_id: str,
    cosmos: CosmosDep,
) -> dict[str, str]:
    from azure.cosmos.exceptions import CosmosResourceNotFoundError
    from fastapi import HTTPException
    try:
        doc = await cosmos.read_item(item=script_id, partition_key=str(project_id))
    except CosmosResourceNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Script not found.")
    return {k: v for k, v in doc.get("scripts", {}).items() if isinstance(v, str)}


@router.get(
    "/{script_id}/versions",
    summary="Return version history entries for a script",
)
async def get_script_versions(
    project_id: uuid.UUID,
    script_id: str,
    cosmos: CosmosDep,
) -> list[dict]:
    from azure.cosmos.exceptions import CosmosResourceNotFoundError
    from fastapi import HTTPException
    try:
        doc = await cosmos.read_item(item=script_id, partition_key=str(project_id))
    except CosmosResourceNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Script not found.")
    current = {
        "version_number": doc.get("version", 1),
        "change_summary": None,
        "is_ai_generated": doc.get("source_job_id") is not None,
        "created_by": doc.get("created_by"),
        "created_at": doc.get("updated_at", doc.get("created_at")),
    }
    history = doc.get("version_history", [])
    return [current, *history]


@router.post(
    "/{script_id}/submit-review",
    response_model=TestScriptRead,
    dependencies=[Depends(RequirePermission(Permission.SCRIPT_UPDATE))],
)
async def submit_review(
    project_id: uuid.UUID, script_id: str, cosmos: CosmosDep, current_user: CurrentUser
) -> TestScriptRead:
    service = TestScriptService(cosmos)
    return await service.submit_for_review(script_id, str(project_id), current_user)


@router.post(
    "/{script_id}/approve",
    response_model=TestScriptRead,
    dependencies=[Depends(RequirePermission(Permission.SCRIPT_APPROVE))],
)
async def approve_script(
    project_id: uuid.UUID,
    script_id: str,
    body: ApprovalRequest,
    cosmos: CosmosDep,
    current_user: CurrentUser,
) -> TestScriptRead:
    service = TestScriptService(cosmos)
    return await service.approve_script(script_id, str(project_id), current_user, body.comments)


@router.post(
    "/{script_id}/reject",
    response_model=TestScriptRead,
    dependencies=[Depends(RequirePermission(Permission.SCRIPT_APPROVE))],
)
async def reject_script(
    project_id: uuid.UUID,
    script_id: str,
    body: RejectionRequest,
    cosmos: CosmosDep,
    current_user: CurrentUser,
) -> TestScriptRead:
    service = TestScriptService(cosmos)
    return await service.reject_script(script_id, str(project_id), current_user, body.comments)


@router.post(
    "/{script_id}/export",
    response_model=ExportResponse,
    dependencies=[Depends(RequirePermission(Permission.SCRIPT_EXPORT))],
    summary="Export a test script (legacy POST — prefer GET /test-scripts/{id}/export)",
    deprecated=True,
)
async def export_script_legacy(
    project_id: uuid.UUID,
    script_id: str,
    body: ExportRequest,
    cosmos: CosmosDep,
    current_user: CurrentUser,
) -> ExportResponse:
    service = TestScriptService(cosmos)
    return await service.export_script(script_id, str(project_id), body)


# ── Script-level export router (no project_id in path) ───────────────────────

export_router = APIRouter(prefix="/test-scripts")


@export_router.get(
    "/{script_id}/export",
    response_model=ExportResponse,
    dependencies=[Depends(RequirePermission(Permission.SCRIPT_EXPORT))],
    summary="Export a test script to the requested format",
)
async def export_script(
    script_id: uuid.UUID,
    db: TenantDB,
    cosmos: CosmosDep,
    current_user: CurrentUser,
    format: ScriptFormat = Query(..., description="Target export format"),
    project_name: str = Query("KAATS", description="Project name for generated file headers"),
    system_url: str = Query("", description="Base URL of the system under test"),
) -> ExportResponse:
    svc = ExportService(db, cosmos)
    export_format = ExportFormat(format.value)
    result = await svc.export_test_script(
        test_script_id=script_id,
        export_format=export_format,
        tenant_id=current_user.tenant_id,
        project_name=project_name,
        system_url=system_url,
    )
    return ExportResponse(
        format=format,
        content=result.content,
        blob_uri=result.blob_uri,
        download_url=result.download_url,
        expires_at=result.expires_at,
        validation_errors=result.validation.errors,
    )


@export_router.post(
    "/export-bulk",
    response_model=BulkExportResponse,
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(RequirePermission(Permission.SCRIPT_EXPORT))],
    summary="Export multiple test scripts as a ZIP archive",
)
async def export_bulk(
    body: BulkExportRequest,
    db: TenantDB,
    cosmos: CosmosDep,
    current_user: CurrentUser,
) -> BulkExportResponse:
    svc = ExportService(db, cosmos)
    result = await svc.export_bulk(
        test_script_ids=body.script_ids,
        export_format=ExportFormat(body.format.value),
        tenant_id=current_user.tenant_id,
        project_name=body.project_name,
        system_url=body.system_url,
    )
    return BulkExportResponse(
        format=body.format,
        blob_uri=result.blob_uri,
        download_url=result.download_url,
        expires_at=result.expires_at,
        file_count=result.file_count,
        generated_at=result.generated_at,
    )


# ── Aggregated export consumed by main.py ────────────────────────────────────
# main.py imports ``router`` — we aggregate both sub-routers so a single
# include_router() call covers all endpoints without touching main.py.

combined_router = APIRouter()
combined_router.include_router(router)
combined_router.include_router(export_router)
