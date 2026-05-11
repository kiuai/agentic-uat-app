"""Requirements ingestion endpoints."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile, status

from app.auth.permissions import Permission
from app.dependencies import CurrentUser, CurrentUserDep, RequirePermission, TenantDB
from app.models.requirement import RequirementStatus
from app.schemas.requirement import RequirementCreate, RequirementRead, RequirementUpdate
from app.services.requirement_service import RequirementService

router = APIRouter(prefix="/projects/{project_id}/requirements")


@router.get(
    "",
    response_model=list[RequirementRead],
    dependencies=[Depends(RequirePermission(Permission.REQUIREMENT_READ))],
)
async def list_requirements(
    project_id: uuid.UUID,
    db: TenantDB,
    current_user: CurrentUserDep,
    status: RequirementStatus | None = Query(None),
    business_domain: str | None = Query(None),
    search: str | None = Query(None, max_length=255),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> list[RequirementRead]:
    service = RequirementService(db)
    return await service.list_requirements(
        project_id,
        current_user.tenant_id,
        status=status,
        business_domain=business_domain,
        search=search,
        limit=limit,
        offset=offset,
    )


@router.post(
    "",
    response_model=RequirementRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(RequirePermission(Permission.REQUIREMENT_CREATE))],
)
async def create_requirement(
    project_id: uuid.UUID,
    body: RequirementCreate,
    db: TenantDB,
    current_user: CurrentUserDep,
) -> RequirementRead:
    service = RequirementService(db)
    return await service.create_requirement(
        project_id, current_user.tenant_id, current_user.id, body
    )


@router.post(
    "/upload",
    response_model=RequirementRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(RequirePermission(Permission.REQUIREMENT_CREATE))],
)
async def upload_requirement(
    project_id: uuid.UUID,
    file: UploadFile = File(...),
    title: str = Form(...),
    business_domain: str | None = Form(None),
    db: TenantDB = Depends(),
    current_user: CurrentUserDep,
) -> RequirementRead:
    service = RequirementService(db)
    return await service.upload_requirement(
        project_id, current_user.tenant_id, current_user.id, file, title, business_domain
    )


@router.get(
    "/{req_id}",
    response_model=RequirementRead,
    dependencies=[Depends(RequirePermission(Permission.REQUIREMENT_READ))],
)
async def get_requirement(
    project_id: uuid.UUID, req_id: uuid.UUID, db: TenantDB
) -> RequirementRead:
    service = RequirementService(db)
    return await service.get_requirement(req_id)


@router.patch(
    "/{req_id}",
    response_model=RequirementRead,
    dependencies=[Depends(RequirePermission(Permission.REQUIREMENT_UPDATE))],
)
async def update_requirement(
    project_id: uuid.UUID, req_id: uuid.UUID, body: RequirementUpdate, db: TenantDB
) -> RequirementRead:
    service = RequirementService(db)
    return await service.update_requirement(req_id, body)


@router.delete(
    "/{req_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(RequirePermission(Permission.REQUIREMENT_DELETE))],
)
async def delete_requirement(
    project_id: uuid.UUID, req_id: uuid.UUID, db: TenantDB
) -> None:
    service = RequirementService(db)
    await service.delete_requirement(req_id)


@router.get(
    "/{req_id}/quality-check",
    dependencies=[Depends(RequirePermission(Permission.REQUIREMENT_READ))],
    summary="Run a heuristic quality check and return a testability score",
)
async def quality_check(
    project_id: uuid.UUID, req_id: uuid.UUID, db: TenantDB
) -> dict[str, Any]:
    service = RequirementService(db)
    return await service.quality_check(req_id)


@router.post(
    "/{req_id}/generate-scripts",
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(RequirePermission(Permission.AI_GENERATE))],
    summary="Dispatch an AI generation job for this requirement",
)
async def generate_scripts(
    project_id: uuid.UUID,
    req_id: uuid.UUID,
    db: TenantDB,
    current_user: CurrentUserDep,
    output_formats: list[str] = Query(
        default=["playwright_ts"],
        description="Script formats to generate",
    ),
) -> dict[str, Any]:
    service = RequirementService(db)
    return await service.trigger_generate_scripts(
        project_id,
        current_user.tenant_id,
        current_user.id,
        req_id,
        output_formats,
    )
