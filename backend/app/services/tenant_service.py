"""Tenant and company management service."""

from __future__ import annotations

import uuid

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.tenant import Company, Enterprise
from app.schemas.tenant import CompanyCreate, CompanyRead, EnterpriseCreate, EnterpriseRead


class TenantService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def list_enterprises(self) -> list[EnterpriseRead]:
        result = await self._db.execute(select(Enterprise).where(Enterprise.is_active == True))
        return [EnterpriseRead.model_validate(e) for e in result.scalars()]

    async def create_enterprise(self, body: EnterpriseCreate) -> EnterpriseRead:
        existing = await self._db.execute(
            select(Enterprise).where(Enterprise.slug == body.slug)
        )
        if existing.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Enterprise slug '{body.slug}' already exists.",
            )
        enterprise = Enterprise(id=uuid.uuid4(), name=body.name, slug=body.slug)
        self._db.add(enterprise)
        await self._db.flush()
        await self._db.refresh(enterprise)
        return EnterpriseRead.model_validate(enterprise)

    async def list_companies(self, enterprise_id: uuid.UUID) -> list[CompanyRead]:
        result = await self._db.execute(
            select(Company).where(
                Company.enterprise_id == enterprise_id,
                Company.is_active == True,
            )
        )
        return [CompanyRead.model_validate(c) for c in result.scalars()]

    async def create_company(
        self, enterprise_id: uuid.UUID, body: CompanyCreate
    ) -> CompanyRead:
        existing = await self._db.execute(
            select(Company).where(Company.slug == body.slug)
        )
        if existing.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Company slug '{body.slug}' already exists.",
            )
        tenant_id = uuid.uuid4()
        company = Company(
            id=uuid.uuid4(),
            enterprise_id=enterprise_id,
            tenant_id=tenant_id,
            name=body.name,
            slug=body.slug,
        )
        self._db.add(company)
        await self._db.flush()
        await self._db.refresh(company)
        return CompanyRead.model_validate(company)
