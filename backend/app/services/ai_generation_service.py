"""AI test generation job service — creates jobs and publishes to Service Bus."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import structlog

from app.models.job import Job, JobStatus, JobType
from app.schemas.ai_generation import GenerationJobRequest
from app.schemas.job import JobRead
from app.services.servicebus_service import ServiceBusService

logger = structlog.get_logger(__name__)


class AIGenerationService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def create_generation_job(
        self,
        project_id: uuid.UUID,
        tenant_id: uuid.UUID,
        user_id: uuid.UUID,
        body: GenerationJobRequest,
    ) -> JobRead:
        input_payload = {
            "requirement_ids": [str(r) for r in body.requirement_ids],
            "output_formats": [f.value for f in body.output_formats],
            "generation_config": body.generation_config.model_dump(),
        }

        job = Job(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            project_id=project_id,
            job_type=JobType.AI_GENERATION,
            status=JobStatus.PENDING,
            created_by=user_id,
            input_payload=json.dumps(input_payload),
        )
        self._db.add(job)
        await self._db.flush()
        await self._db.refresh(job)

        await ServiceBusService().publish_ai_job(
            job_id=str(job.id),
            tenant_id=str(tenant_id),
            payload=input_payload,
        )

        logger.info("ai_generation_job_created", job_id=str(job.id), tenant_id=str(tenant_id))
        return JobRead.model_validate(job)

    async def list_jobs(
        self, project_id: uuid.UUID, tenant_id: uuid.UUID
    ) -> list[JobRead]:
        result = await self._db.execute(
            select(Job).where(
                Job.project_id == project_id,
                Job.tenant_id == tenant_id,
                Job.job_type == JobType.AI_GENERATION,
            ).order_by(Job.created_at.desc())
        )
        return [JobRead.model_validate(j) for j in result.scalars()]

    async def get_job(self, job_id: uuid.UUID) -> JobRead:
        job = await self._db.get(Job, job_id)
        if not job:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found.")
        return JobRead.model_validate(job)

    async def cancel_job(self, job_id: uuid.UUID) -> None:
        job = await self._db.get(Job, job_id)
        if not job:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found.")
        if job.status not in (JobStatus.PENDING, JobStatus.PROCESSING):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Cannot cancel job in status '{job.status.value}'.",
            )
        job.status = JobStatus.CANCELLED
        job.completed_at = datetime.now(timezone.utc)
        await self._db.flush()
