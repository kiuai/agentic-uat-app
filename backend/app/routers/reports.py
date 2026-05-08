"""Reporting endpoints."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.auth.permissions import Permission
from app.dependencies import CurrentUser, RequirePermission, TenantDB

router = APIRouter(prefix="/projects/{project_id}/reports")


class ProjectSummaryReport(BaseModel):
    project_id: uuid.UUID
    total_scripts: int
    approved_scripts: int
    total_cycles: int
    active_cycles: int
    total_executions: int
    passed: int
    failed: int
    blocked: int
    not_started: int
    pass_rate: float


@router.get(
    "/summary",
    response_model=ProjectSummaryReport,
    dependencies=[Depends(RequirePermission(Permission.REPORT_READ))],
)
async def project_summary(
    project_id: uuid.UUID, db: TenantDB, current_user: CurrentUser
) -> ProjectSummaryReport:
    from app.services.project_service import ProjectService
    service = ProjectService(db)
    return await service.get_summary_report(project_id, current_user.tenant_id)
