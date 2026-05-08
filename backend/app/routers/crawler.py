"""Crawler job endpoints."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, status

from app.auth.permissions import Permission
from app.dependencies import CurrentUser, RequirePermission, TenantDB
from app.schemas.ai_generation import CrawlJobRequest
from app.schemas.job import JobRead
from app.services.crawler_service import CrawlerService

router = APIRouter(prefix="/projects/{project_id}/crawl-jobs")


@router.post(
    "",
    response_model=JobRead,
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(RequirePermission(Permission.CRAWLER_TRIGGER))],
)
async def trigger_crawl(
    project_id: uuid.UUID,
    body: CrawlJobRequest,
    db: TenantDB,
    current_user: CurrentUser,
) -> JobRead:
    service = CrawlerService(db)
    return await service.create_crawl_job(
        project_id, current_user.tenant_id, current_user.id, body
    )


@router.get(
    "",
    response_model=list[JobRead],
    dependencies=[Depends(RequirePermission(Permission.CRAWLER_READ))],
)
async def list_crawl_jobs(
    project_id: uuid.UUID, db: TenantDB, current_user: CurrentUser
) -> list[JobRead]:
    service = CrawlerService(db)
    return await service.list_jobs(project_id, current_user.tenant_id)


@router.get(
    "/{job_id}",
    response_model=JobRead,
    dependencies=[Depends(RequirePermission(Permission.CRAWLER_READ))],
)
async def get_crawl_job(
    project_id: uuid.UUID, job_id: uuid.UUID, db: TenantDB
) -> JobRead:
    service = CrawlerService(db)
    return await service.get_job(job_id)


@router.delete(
    "/{job_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(RequirePermission(Permission.CRAWLER_TRIGGER))],
)
async def cancel_crawl_job(
    project_id: uuid.UUID, job_id: uuid.UUID, db: TenantDB
) -> None:
    service = CrawlerService(db)
    await service.cancel_job(job_id)
