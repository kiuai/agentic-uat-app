"""Requirements ingestion endpoints."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status

from app.auth.permissions import Permission
from app.dependencies import CurrentUser, RequirePermission, TenantDB
from app.schemas.requirement import RequirementCreate, RequirementRead, RequirementUpdate
from app.services.requirement_service import RequirementService

router = APIRouter(prefix="/projects/{project_id}/requirements")


@router.get(
    "",
    response_model=list[RequirementRead],
    dependencies=[Depends(RequirePermission(Permission.REQUIREMENT_READ))],
)
async def list_requirements(
    project_id: uuid.UUID, db: TenantDB, current_user: CurrentUser
) -> list[RequirementRead]:
    service = RequirementService(db)
    return await service.list_requirements(project_id, current_user.tenant_id)


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
    current_user: CurrentUser,
) -> RequirementRead:
    service = RequirementService(db)
    return await service.create_requirement(project_id, current_user.tenant_id, current_user.id, body)


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
    domain_code: str | None = Form(None),
    db: TenantDB = Depends(),
    current_user: CurrentUser = Depends(),
) -> RequirementRead:
    service = RequirementService(db)
    return await service.upload_requirement(
        project_id, current_user.tenant_id, current_user.id, file, title, domain_code
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
