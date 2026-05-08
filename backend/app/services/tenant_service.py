"""Tenant and company management service."""

from __future__ import annotations

import uuid

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.tenant import BusinessDomain, Company, Enterprise
from app.schemas.tenant import (
    BusinessDomainCreate,
    BusinessDomainResponse,
    BusinessDomainUpdate,
    CompanyCreate,
    CompanyResponse,
    CompanyUpdate,
    EnterpriseCreate,
    EnterpriseResponse,
    EnterpriseUpdate,
)

# Backward-compat aliases
EnterpriseRead = EnterpriseResponse
CompanyRead = CompanyResponse


class TenantService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    # ── Enterprise ────────────────────────────────────────────────────────────

    async def list_enterprises(self) -> list[EnterpriseResponse]:
        result = await self._db.execute(select(Enterprise).where(Enterprise.is_active == True))
        return [EnterpriseResponse.model_validate(e) for e in result.scalars()]

    async def create_enterprise(self, body: EnterpriseCreate) -> EnterpriseResponse:
        existing = await self._db.scalar(
            select(Enterprise).where(Enterprise.slug == body.slug)
        )
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Enterprise slug '{body.slug}' already exists.",
            )
        enterprise = Enterprise(
            id=uuid.uuid4(),
            name=body.name,
            slug=body.slug,
            azure_ad_tenant_id=body.azure_ad_tenant_id,
            settings=body.settings,
            is_active=body.is_active,
        )
        self._db.add(enterprise)
        await self._db.flush()
        await self._db.refresh(enterprise)
        return EnterpriseResponse.model_validate(enterprise)

    async def get_enterprise(self, enterprise_id: uuid.UUID) -> EnterpriseResponse:
        enterprise = await self._db.get(Enterprise, enterprise_id)
        if not enterprise:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Enterprise not found.")
        return EnterpriseResponse.model_validate(enterprise)

    async def update_enterprise(
        self, enterprise_id: uuid.UUID, body: EnterpriseUpdate
    ) -> EnterpriseResponse:
        enterprise = await self._db.get(Enterprise, enterprise_id)
        if not enterprise:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Enterprise not found.")
        for field, value in body.model_dump(exclude_none=True).items():
            setattr(enterprise, field, value)
        await self._db.flush()
        await self._db.refresh(enterprise)
        return EnterpriseResponse.model_validate(enterprise)

    async def soft_delete_enterprise(self, enterprise_id: uuid.UUID) -> None:
        enterprise = await self._db.get(Enterprise, enterprise_id)
        if not enterprise:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Enterprise not found.")
        enterprise.is_active = False
        await self._db.flush()

    # ── Company ───────────────────────────────────────────────────────────────

    async def list_companies(self, enterprise_id: uuid.UUID) -> list[CompanyResponse]:
        result = await self._db.execute(
            select(Company).where(
                Company.enterprise_id == enterprise_id,
                Company.is_active == True,
            )
        )
        return [CompanyResponse.model_validate(c) for c in result.scalars()]

    async def get_company(self, company_id: uuid.UUID) -> CompanyResponse:
        company = await self._db.get(Company, company_id)
        if not company:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Company not found.")
        return CompanyResponse.model_validate(company)

    async def create_company(
        self, enterprise_id: uuid.UUID, body: CompanyCreate
    ) -> CompanyResponse:
        existing = await self._db.scalar(
            select(Company).where(
                Company.enterprise_id == enterprise_id,
                Company.slug == body.slug,
            )
        )
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Company slug '{body.slug}' already exists in this enterprise.",
            )
        tenant_id = uuid.uuid4()
        company = Company(
            id=uuid.uuid4(),
            enterprise_id=enterprise_id,
            tenant_id=tenant_id,
            name=body.name,
            slug=body.slug,
            settings=body.settings,
            is_active=body.is_active,
        )
        self._db.add(company)
        await self._db.flush()
        await self._db.refresh(company)
        return CompanyResponse.model_validate(company)

    async def update_company(
        self, company_id: uuid.UUID, body: CompanyUpdate
    ) -> CompanyResponse:
        company = await self._db.get(Company, company_id)
        if not company:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Company not found.")
        for field, value in body.model_dump(exclude_none=True).items():
            setattr(company, field, value)
        await self._db.flush()
        await self._db.refresh(company)
        return CompanyResponse.model_validate(company)

    async def soft_delete_company(self, company_id: uuid.UUID) -> None:
        company = await self._db.get(Company, company_id)
        if not company:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Company not found.")
        company.is_active = False
        await self._db.flush()

    # ── Business Domains ──────────────────────────────────────────────────────

    async def list_business_domains(self, tenant_id: uuid.UUID) -> list[BusinessDomainResponse]:
        result = await self._db.execute(
            select(BusinessDomain).where(
                BusinessDomain.tenant_id == tenant_id,
                BusinessDomain.is_active == True,
            ).order_by(BusinessDomain.name)
        )
        return [BusinessDomainResponse.model_validate(d) for d in result.scalars()]

    async def create_business_domain(
        self, tenant_id: uuid.UUID, body: BusinessDomainCreate
    ) -> BusinessDomainResponse:
        existing = await self._db.scalar(
            select(BusinessDomain).where(
                BusinessDomain.tenant_id == tenant_id,
                BusinessDomain.code == body.code,
            )
        )
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Business domain code '{body.code}' already exists in this tenant.",
            )
        domain = BusinessDomain(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            name=body.name,
            code=body.code,
            description=body.description,
            is_active=body.is_active,
        )
        self._db.add(domain)
        await self._db.flush()
        await self._db.refresh(domain)
        return BusinessDomainResponse.model_validate(domain)

    async def update_business_domain(
        self, domain_id: uuid.UUID, body: BusinessDomainUpdate
    ) -> BusinessDomainResponse:
        domain = await self._db.get(BusinessDomain, domain_id)
        if not domain:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Business domain not found.")
        for field, value in body.model_dump(exclude_none=True).items():
            setattr(domain, field, value)
        await self._db.flush()
        await self._db.refresh(domain)
        return BusinessDomainResponse.model_validate(domain)

    async def delete_business_domain(self, domain_id: uuid.UUID) -> None:
        domain = await self._db.get(BusinessDomain, domain_id)
        if not domain:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Business domain not found.")
        domain.is_active = False
        await self._db.flush()
