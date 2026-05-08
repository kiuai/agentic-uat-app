"""Crawler job endpoints.

Route layout (mounted under /api/v1):
  POST   /projects/{project_id}/crawl            — start a crawl job
  GET    /projects/{project_id}/crawl-jobs       — list crawl jobs for a project
  GET    /crawl-jobs/{job_id}                    — get job status (no project_id needed)
  GET    /crawl-jobs/{job_id}/pages              — list discovered pages
  POST   /crawl-jobs/{job_id}/cancel             — cancel a running job
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, status

from app.auth.permissions import Permission
from app.dependencies import CurrentUser, RequirePermission, TenantDB
from app.schemas.crawl_job import CrawlJobCreate, CrawlJobResponse, CrawlPageResponse
from app.services.crawler_service import CrawlerService

# ── Project-scoped routes ─────────────────────────────────────────────────────

project_router = APIRouter(prefix="/projects/{project_id}")


@project_router.post(
    "/crawl",
    response_model=CrawlJobResponse,
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(RequirePermission(Permission.CRAWLER_CREATE))],
    summary="Start a crawl job",
)
async def start_crawl(
    project_id: uuid.UUID,
    body: CrawlJobCreate,
    db: TenantDB,
    current_user: CurrentUser,
) -> CrawlJobResponse:
    service = CrawlerService(db)
    return await service.start_crawl_job(
        project_id=project_id,
        tenant_id=current_user.tenant_id,
        user_id=current_user.id,
        body=body,
    )


@project_router.get(
    "/crawl-jobs",
    response_model=list[CrawlJobResponse],
    dependencies=[Depends(RequirePermission(Permission.CRAWLER_READ))],
    summary="List crawl jobs for a project",
)
async def list_crawl_jobs(
    project_id: uuid.UUID,
    db: TenantDB,
    current_user: CurrentUser,
) -> list[CrawlJobResponse]:
    service = CrawlerService(db)
    return await service.list_jobs(project_id, current_user.tenant_id)


# ── Job-level routes (no project_id in path) ──────────────────────────────────

job_router = APIRouter(prefix="/crawl-jobs")


@job_router.get(
    "/{job_id}",
    response_model=CrawlJobResponse,
    dependencies=[Depends(RequirePermission(Permission.CRAWLER_READ))],
    summary="Get crawl job status",
)
async def get_crawl_job(
    job_id: uuid.UUID,
    db: TenantDB,
) -> CrawlJobResponse:
    service = CrawlerService(db)
    return await service.get_job(job_id)


@job_router.get(
    "/{job_id}/pages",
    response_model=list[CrawlPageResponse],
    dependencies=[Depends(RequirePermission(Permission.CRAWLER_READ))],
    summary="List pages discovered by a crawl job",
)
async def get_crawl_pages(
    job_id: uuid.UUID,
    db: TenantDB,
    current_user: CurrentUser,
) -> list[CrawlPageResponse]:
    service = CrawlerService(db)
    return await service.get_crawl_results(job_id, current_user.tenant_id)


@job_router.post(
    "/{job_id}/cancel",
    response_model=CrawlJobResponse,
    dependencies=[Depends(RequirePermission(Permission.CRAWLER_CANCEL))],
    summary="Cancel a pending or running crawl job",
)
async def cancel_crawl_job(
    job_id: uuid.UUID,
    db: TenantDB,
    current_user: CurrentUser,
) -> CrawlJobResponse:
    service = CrawlerService(db)
    return await service.cancel_job(job_id, current_user.tenant_id)


# ── Single export consumed by main.py ─────────────────────────────────────────
# ``router`` is kept for the existing include_router call; it aggregates both
# sub-routers so main.py needs no changes.

router = APIRouter()
router.include_router(project_router)
router.include_router(job_router)
