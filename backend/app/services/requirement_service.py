"""Requirement ingestion service."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.requirement import Requirement, RequirementSourceType, RequirementStatus
from app.schemas.requirement import RequirementCreate, RequirementRead, RequirementUpdate


class RequirementService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def list_requirements(
        self,
        project_id: uuid.UUID,
        tenant_id: uuid.UUID,
        *,
        status: RequirementStatus | None = None,
        business_domain: str | None = None,
        search: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[RequirementRead]:
        stmt = select(Requirement).where(
            Requirement.project_id == project_id,
            Requirement.tenant_id == tenant_id,
        )
        if status:
            stmt = stmt.where(Requirement.status == status)
        if business_domain:
            stmt = stmt.where(Requirement.business_domain == business_domain)
        if search:
            stmt = stmt.where(Requirement.title.ilike(f"%{search}%"))
        stmt = stmt.order_by(Requirement.created_at.desc()).offset(offset).limit(limit)
        result = await self._db.execute(stmt)
        return [RequirementRead.model_validate(r) for r in result.scalars()]

    async def create_requirement(
        self,
        project_id: uuid.UUID,
        tenant_id: uuid.UUID,
        user_id: uuid.UUID,
        body: RequirementCreate,
    ) -> RequirementRead:
        req = Requirement(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            project_id=project_id,
            title=body.title,
            description=body.description,
            source_type=body.source_type,
            content_text=body.content_text,
            source_ref=body.source_ref,
            business_domain=body.business_domain,
            priority=body.priority,
            tags=body.tags or [],
            status=RequirementStatus.PENDING,
            uploaded_by=user_id,
        )
        self._db.add(req)
        await self._db.flush()
        await self._db.refresh(req)
        return RequirementRead.model_validate(req)

    async def upload_requirement(
        self,
        project_id: uuid.UUID,
        tenant_id: uuid.UUID,
        user_id: uuid.UUID,
        file: UploadFile,
        title: str,
        business_domain: str | None,
    ) -> RequirementRead:
        from app.services.blob_service import BlobService

        ext = (file.filename or "").rsplit(".", 1)[-1].lower()
        source_type_map = {"pdf": RequirementSourceType.PDF, "docx": RequirementSourceType.DOCX}
        source_type = source_type_map.get(ext, RequirementSourceType.TEXT)

        blob_service = BlobService()
        blob_path = f"{tenant_id}/requirements/{uuid.uuid4()}/{file.filename}"
        content = await file.read()
        blob_uri = await blob_service.upload(
            tenant_id, blob_path, content, file.content_type or "application/octet-stream"
        )

        req = Requirement(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            project_id=project_id,
            title=title,
            source_type=source_type,
            blob_uri=blob_uri,
            business_domain=business_domain,
            status=RequirementStatus.PENDING,
            uploaded_by=user_id,
        )
        self._db.add(req)
        await self._db.flush()
        await self._db.refresh(req)
        return RequirementRead.model_validate(req)

    async def get_requirement(self, req_id: uuid.UUID) -> RequirementRead:
        req = await self._db.get(Requirement, req_id)
        if not req:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Requirement not found.")
        return RequirementRead.model_validate(req)

    async def update_requirement(
        self, req_id: uuid.UUID, body: RequirementUpdate
    ) -> RequirementRead:
        req = await self._db.get(Requirement, req_id)
        if not req:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Requirement not found.")
        for field, value in body.model_dump(exclude_none=True).items():
            setattr(req, field, value)
        await self._db.flush()
        await self._db.refresh(req)
        return RequirementRead.model_validate(req)

    async def delete_requirement(self, req_id: uuid.UUID) -> None:
        req = await self._db.get(Requirement, req_id)
        if not req:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Requirement not found.")
        await self._db.delete(req)
        await self._db.flush()

    async def quality_check(self, req_id: uuid.UUID) -> dict[str, Any]:
        """
        Run a lightweight heuristic quality check on a requirement.

        Returns a dict with ``score`` (0-100), ``verdict``, and ``issues``.
        A full AI-powered check runs via the AI generation pipeline; this
        endpoint provides instant feedback without a job queue round-trip.
        """
        req = await self._db.get(Requirement, req_id)
        if not req:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Requirement not found.")

        issues: list[str] = []
        score = 100

        content = req.content_text or req.description or ""
        title = req.title or ""

        if len(title) < 10:
            issues.append("Title is too short — add more context.")
            score -= 20
        if len(content) < 30:
            issues.append("Content is very short — detailed requirements improve test quality.")
            score -= 30
        if not content:
            issues.append("No content text — provide a description or upload a document.")
            score -= 40
        if not req.business_domain:
            issues.append("No business domain assigned — add one to enable BPO scoping.")
            score -= 5
        keywords = ["shall", "must", "should", "will", "verify", "validate", "ensure"]
        if not any(kw in content.lower() for kw in keywords):
            issues.append("Requirement lacks testability keywords (shall, must, verify, etc.).")
            score -= 15

        score = max(0, score)
        if score >= 70:
            verdict = "TESTABLE"
        elif score >= 40:
            verdict = "NEEDS_IMPROVEMENT"
        else:
            verdict = "UNTESTABLE"

        return {
            "requirement_id": str(req_id),
            "score": score,
            "verdict": verdict,
            "issues": issues,
        }

    async def trigger_generate_scripts(
        self,
        project_id: uuid.UUID,
        tenant_id: uuid.UUID,
        user_id: uuid.UUID,
        req_id: uuid.UUID,
        output_formats: list[str] | None = None,
    ) -> dict[str, Any]:
        """
        Dispatch an AI generation job for a single requirement.

        Creates a Job row and publishes to Service Bus.
        Returns the job metadata so the caller can poll for completion.
        """
        req = await self._db.get(Requirement, req_id)
        if not req:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Requirement not found.")
        if req.status == RequirementStatus.PROCESSED:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Requirement already has generated scripts.",
            )

        from app.models.job import Job, JobStatus, JobType
        import json

        job = Job(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            project_id=project_id,
            job_type=JobType.AI_GENERATION,
            status=JobStatus.PENDING,
            input_payload=json.dumps({
                "requirement_ids": [str(req_id)],
                "output_formats": output_formats or ["playwright_ts"],
            }),
            created_by=user_id,
        )
        self._db.add(job)
        await self._db.flush()

        # Dispatch to Service Bus
        try:
            from app.services.servicebus_service import ServiceBusService
            sbs = ServiceBusService()
            await sbs.publish_ai_job(
                job_id=str(job.id),
                tenant_id=str(tenant_id),
                project_id=str(project_id),
                payload={"requirement_ids": [str(req_id)], "output_formats": output_formats or ["playwright_ts"]},
            )
        except Exception:
            pass  # Job row created; worker retry or manual re-trigger

        return {"job_id": str(job.id), "status": job.status.value}
