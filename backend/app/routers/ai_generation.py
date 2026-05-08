"""AI test generation job endpoints."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, status
from fastapi.responses import StreamingResponse

from app.auth.permissions import Permission
from app.dependencies import CurrentUser, RequirePermission, TenantDB
from app.schemas.ai_generation import GenerationJobRequest
from app.schemas.job import JobRead
from app.services.ai_generation_service import AIGenerationService

router = APIRouter(prefix="/projects/{project_id}/generation-jobs")


@router.post(
    "",
    response_model=JobRead,
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(RequirePermission(Permission.AI_GENERATION_TRIGGER))],
)
async def trigger_generation(
    project_id: uuid.UUID,
    body: GenerationJobRequest,
    db: TenantDB,
    current_user: CurrentUser,
) -> JobRead:
    service = AIGenerationService(db)
    return await service.create_generation_job(
        project_id, current_user.tenant_id, current_user.id, body
    )


@router.get(
    "",
    response_model=list[JobRead],
    dependencies=[Depends(RequirePermission(Permission.AI_GENERATION_READ))],
)
async def list_generation_jobs(
    project_id: uuid.UUID, db: TenantDB, current_user: CurrentUser
) -> list[JobRead]:
    service = AIGenerationService(db)
    return await service.list_jobs(project_id, current_user.tenant_id)


@router.get(
    "/{job_id}",
    response_model=JobRead,
    dependencies=[Depends(RequirePermission(Permission.AI_GENERATION_READ))],
)
async def get_generation_job(
    project_id: uuid.UUID, job_id: uuid.UUID, db: TenantDB
) -> JobRead:
    service = AIGenerationService(db)
    return await service.get_job(job_id)


@router.delete(
    "/{job_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(RequirePermission(Permission.AI_GENERATION_TRIGGER))],
)
async def cancel_generation_job(
    project_id: uuid.UUID, job_id: uuid.UUID, db: TenantDB
) -> None:
    service = AIGenerationService(db)
    await service.cancel_job(job_id)


# ── Generic job status (any job type) ─────────────────────────────────────────

generic_router = APIRouter(prefix="/jobs")


@generic_router.get("/{job_id}", response_model=JobRead)
async def get_job(job_id: uuid.UUID, db: TenantDB, current_user: CurrentUser) -> JobRead:
    """Universal job status endpoint for any job type."""
    service = AIGenerationService(db)
    return await service.get_job(job_id)
