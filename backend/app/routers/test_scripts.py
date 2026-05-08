"""Test script repository endpoints."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, status

from app.auth.permissions import Permission
from app.dependencies import CurrentUser, CosmosDep, RequirePermission, TenantDB
from app.schemas.test_script import (
    ApprovalRequest,
    ExportRequest,
    ExportResponse,
    RejectionRequest,
    TestScriptCreate,
    TestScriptRead,
    TestScriptUpdate,
)
from app.services.test_script_service import TestScriptService

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


@router.post(
    "/{script_id}/submit-review",
    response_model=TestScriptRead,
    dependencies=[Depends(RequirePermission(Permission.SCRIPT_SUBMIT))],
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
)
async def export_script(
    project_id: uuid.UUID,
    script_id: str,
    body: ExportRequest,
    cosmos: CosmosDep,
    current_user: CurrentUser,
) -> ExportResponse:
    service = TestScriptService(cosmos)
    return await service.export_script(script_id, str(project_id), body)
