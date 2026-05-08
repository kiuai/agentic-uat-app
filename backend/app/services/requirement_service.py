"""Requirement ingestion service."""

from __future__ import annotations

import uuid

from fastapi import HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.requirement import Requirement, RequirementSourceType, RequirementStatus
from app.schemas.requirement import RequirementCreate, RequirementRead, RequirementUpdate


class RequirementService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def list_requirements(
        self, project_id: uuid.UUID, tenant_id: uuid.UUID
    ) -> list[RequirementRead]:
        result = await self._db.execute(
            select(Requirement).where(
                Requirement.project_id == project_id,
                Requirement.tenant_id == tenant_id,
            )
        )
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
            source_type=body.source_type,
            content_text=body.content_text,
            source_ref=body.source_ref,
            domain_code=body.domain_code,
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
        domain_code: str | None,
    ) -> RequirementRead:
        from app.services.blob_service import BlobService

        ext = (file.filename or "").rsplit(".", 1)[-1].lower()
        source_type_map = {"pdf": RequirementSourceType.PDF, "docx": RequirementSourceType.DOCX}
        source_type = source_type_map.get(ext, RequirementSourceType.TEXT)

        blob_service = BlobService()
        blob_path = f"{tenant_id}/requirements/{uuid.uuid4()}/{file.filename}"
        content = await file.read()
        blob_uri = await blob_service.upload(tenant_id, blob_path, content, file.content_type or "application/octet-stream")

        req = Requirement(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            project_id=project_id,
            title=title,
            source_type=source_type,
            blob_uri=blob_uri,
            domain_code=domain_code,
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
