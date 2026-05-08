"""Reporting endpoints."""

from __future__ import annotations

import uuid
from datetime import date, datetime

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from app.auth.permissions import Permission
from app.dependencies import CurrentUser, RequirePermission, TenantDB

router = APIRouter(prefix="/projects/{project_id}/reports")


from app.services.project_service import ProjectSummaryReport


# ---------------------------------------------------------------------------
# Additional report schemas
# ---------------------------------------------------------------------------


class ScriptCoverageReport(BaseModel):
    project_id: uuid.UUID
    total_requirements: int
    requirements_with_scripts: int
    coverage_percent: float
    requirements_without_scripts: list[str]


class CycleSummaryReport(BaseModel):
    cycle_id: uuid.UUID
    cycle_name: str
    status: str
    total_assignments: int
    passed: int
    failed: int
    blocked: int
    not_started: int
    in_progress: int
    pass_rate: float
    started_at: date | None
    completed_at: date | None


class AIUsageReport(BaseModel):
    project_id: uuid.UUID
    total_jobs: int
    completed_jobs: int
    failed_jobs: int
    total_scripts_generated: int
    generated_at: datetime


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


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


@router.get(
    "/coverage",
    response_model=ScriptCoverageReport,
    dependencies=[Depends(RequirePermission(Permission.REPORT_READ))],
    summary="Script coverage — which requirements have generated test scripts",
)
async def script_coverage(
    project_id: uuid.UUID, db: TenantDB, current_user: CurrentUser
) -> ScriptCoverageReport:
    from sqlalchemy import func, select
    from app.models.requirement import Requirement
    from app.models.test_script import TestScript

    total = await db.scalar(
        select(func.count(Requirement.id)).where(
            Requirement.project_id == project_id,
            Requirement.tenant_id == current_user.tenant_id,
        )
    ) or 0

    # Requirements that have at least one script
    covered_result = await db.execute(
        select(TestScript.requirement_id)
        .where(
            TestScript.project_id == project_id,
            TestScript.tenant_id == current_user.tenant_id,
        )
        .distinct()
    )
    covered_ids = {str(r[0]) for r in covered_result}

    # Requirements without scripts
    uncovered_result = await db.execute(
        select(Requirement.id, Requirement.title).where(
            Requirement.project_id == project_id,
            Requirement.tenant_id == current_user.tenant_id,
            ~Requirement.id.in_([uuid.UUID(i) for i in covered_ids]),
        )
    )
    uncovered = [f"{r[0]} – {r[1]}" for r in uncovered_result]

    coverage_pct = round(len(covered_ids) / total * 100, 1) if total else 0.0
    return ScriptCoverageReport(
        project_id=project_id,
        total_requirements=total,
        requirements_with_scripts=len(covered_ids),
        coverage_percent=coverage_pct,
        requirements_without_scripts=uncovered,
    )


@router.get(
    "/cycles/{cycle_id}/summary",
    response_model=CycleSummaryReport,
    dependencies=[Depends(RequirePermission(Permission.REPORT_READ))],
    summary="Execution pass/fail breakdown for a specific test cycle",
)
async def cycle_summary(
    project_id: uuid.UUID,
    cycle_id: uuid.UUID,
    db: TenantDB,
    current_user: CurrentUser,
) -> CycleSummaryReport:
    from sqlalchemy import func, select
    from app.models.test_cycle import ExecutionStatus, TestAssignment, TestCycle

    cycle = await db.get(TestCycle, cycle_id)
    if not cycle:
        from fastapi import HTTPException, status
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cycle not found.")

    counts: dict[str, int] = {}
    for es in ExecutionStatus:
        count = await db.scalar(
            select(func.count(TestAssignment.id)).where(
                TestAssignment.cycle_id == cycle_id,
                TestAssignment.status == es,
            )
        ) or 0
        counts[es.value] = count

    total = sum(counts.values())
    passed = counts.get("PASSED", 0)
    pass_rate = round(passed / total * 100, 1) if total else 0.0

    return CycleSummaryReport(
        cycle_id=cycle_id,
        cycle_name=cycle.name,
        status=cycle.status.value,
        total_assignments=total,
        passed=passed,
        failed=counts.get("FAILED", 0),
        blocked=counts.get("BLOCKED", 0),
        not_started=counts.get("NOT_STARTED", 0),
        in_progress=counts.get("IN_PROGRESS", 0),
        pass_rate=pass_rate,
        started_at=cycle.actual_start_date,
        completed_at=cycle.actual_end_date,
    )


@router.get(
    "/ai-usage",
    response_model=AIUsageReport,
    dependencies=[Depends(RequirePermission(Permission.REPORT_READ))],
    summary="AI generation job counts and script output totals for this project",
)
async def ai_usage(
    project_id: uuid.UUID, db: TenantDB, current_user: CurrentUser
) -> AIUsageReport:
    from datetime import timezone
    from sqlalchemy import func, select
    from app.models.job import Job, JobStatus
    from app.models.test_script import TestScript

    total_jobs = await db.scalar(
        select(func.count(Job.id)).where(Job.project_id == project_id)
    ) or 0
    completed = await db.scalar(
        select(func.count(Job.id)).where(
            Job.project_id == project_id, Job.status == JobStatus.COMPLETED
        )
    ) or 0
    failed = await db.scalar(
        select(func.count(Job.id)).where(
            Job.project_id == project_id, Job.status == JobStatus.FAILED
        )
    ) or 0
    scripts_generated = await db.scalar(
        select(func.count(TestScript.id)).where(
            TestScript.project_id == project_id,
            TestScript.tenant_id == current_user.tenant_id,
            TestScript.is_ai_generated == True,
        )
    ) or 0

    return AIUsageReport(
        project_id=project_id,
        total_jobs=total_jobs,
        completed_jobs=completed,
        failed_jobs=failed,
        total_scripts_generated=scripts_generated,
        generated_at=datetime.now(timezone.utc),
    )
