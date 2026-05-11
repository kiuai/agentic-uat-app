"""Tenant management endpoints (Global and Enterprise Admins)."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, status

from app.auth.permissions import Permission
from app.dependencies import CurrentUser, CurrentUserDep, RequirePermission, TenantDB
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
from app.services.tenant_service import TenantService

router = APIRouter(prefix="/admin")


# ── Enterprise ────────────────────────────────────────────────────────────────

@router.get(
    "/enterprises",
    response_model=list[EnterpriseResponse],
    dependencies=[Depends(RequirePermission(Permission.ADMIN_GLOBAL))],
)
async def list_enterprises(db: TenantDB) -> list[EnterpriseResponse]:
    service = TenantService(db)
    return await service.list_enterprises()


@router.post(
    "/enterprises",
    response_model=EnterpriseResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(RequirePermission(Permission.TENANT_CREATE))],
)
async def create_enterprise(body: EnterpriseCreate, db: TenantDB) -> EnterpriseResponse:
    service = TenantService(db)
    return await service.create_enterprise(body)


@router.get(
    "/enterprises/{enterprise_id}",
    response_model=EnterpriseResponse,
    dependencies=[Depends(RequirePermission(Permission.ADMIN_ENTERPRISE))],
)
async def get_enterprise(enterprise_id: uuid.UUID, db: TenantDB) -> EnterpriseResponse:
    service = TenantService(db)
    return await service.get_enterprise(enterprise_id)


@router.patch(
    "/enterprises/{enterprise_id}",
    response_model=EnterpriseResponse,
    dependencies=[Depends(RequirePermission(Permission.TENANT_UPDATE))],
)
async def update_enterprise(
    enterprise_id: uuid.UUID, body: EnterpriseUpdate, db: TenantDB
) -> EnterpriseResponse:
    service = TenantService(db)
    return await service.update_enterprise(enterprise_id, body)


@router.delete(
    "/enterprises/{enterprise_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(RequirePermission(Permission.TENANT_DELETE))],
)
async def delete_enterprise(enterprise_id: uuid.UUID, db: TenantDB) -> None:
    service = TenantService(db)
    await service.soft_delete_enterprise(enterprise_id)


# ── Company ───────────────────────────────────────────────────────────────────

@router.get(
    "/enterprises/{enterprise_id}/companies",
    response_model=list[CompanyResponse],
    dependencies=[Depends(RequirePermission(Permission.ADMIN_ENTERPRISE))],
)
async def list_companies(enterprise_id: uuid.UUID, db: TenantDB) -> list[CompanyResponse]:
    service = TenantService(db)
    return await service.list_companies(enterprise_id)


@router.post(
    "/enterprises/{enterprise_id}/companies",
    response_model=CompanyResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(RequirePermission(Permission.TENANT_CREATE))],
)
async def create_company(
    enterprise_id: uuid.UUID, body: CompanyCreate, db: TenantDB
) -> CompanyResponse:
    service = TenantService(db)
    return await service.create_company(enterprise_id, body)


@router.get(
    "/companies/{company_id}",
    response_model=CompanyResponse,
    dependencies=[Depends(RequirePermission(Permission.ADMIN_COMPANY))],
)
async def get_company(company_id: uuid.UUID, db: TenantDB) -> CompanyResponse:
    service = TenantService(db)
    return await service.get_company(company_id)


@router.patch(
    "/companies/{company_id}",
    response_model=CompanyResponse,
    dependencies=[Depends(RequirePermission(Permission.TENANT_UPDATE))],
)
async def update_company(
    company_id: uuid.UUID, body: CompanyUpdate, db: TenantDB
) -> CompanyResponse:
    service = TenantService(db)
    return await service.update_company(company_id, body)


@router.delete(
    "/companies/{company_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(RequirePermission(Permission.TENANT_DELETE))],
)
async def delete_company(company_id: uuid.UUID, db: TenantDB) -> None:
    service = TenantService(db)
    await service.soft_delete_company(company_id)


# ── Business Domains ──────────────────────────────────────────────────────────

@router.get(
    "/domains",
    response_model=list[BusinessDomainResponse],
    dependencies=[Depends(RequirePermission(Permission.ADMIN_COMPANY))],
)
async def list_business_domains(
    db: TenantDB, current_user: CurrentUserDep
) -> list[BusinessDomainResponse]:
    service = TenantService(db)
    return await service.list_business_domains(current_user.tenant_id)


@router.post(
    "/domains",
    response_model=BusinessDomainResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(RequirePermission(Permission.ADMIN_COMPANY))],
)
async def create_business_domain(
    body: BusinessDomainCreate, db: TenantDB, current_user: CurrentUserDep
) -> BusinessDomainResponse:
    service = TenantService(db)
    return await service.create_business_domain(current_user.tenant_id, body)


@router.patch(
    "/domains/{domain_id}",
    response_model=BusinessDomainResponse,
    dependencies=[Depends(RequirePermission(Permission.ADMIN_COMPANY))],
)
async def update_business_domain(
    domain_id: uuid.UUID, body: BusinessDomainUpdate, db: TenantDB
) -> BusinessDomainResponse:
    service = TenantService(db)
    return await service.update_business_domain(domain_id, body)


@router.delete(
    "/domains/{domain_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(RequirePermission(Permission.ADMIN_COMPANY))],
)
async def delete_business_domain(domain_id: uuid.UUID, db: TenantDB) -> None:
    service = TenantService(db)
    await service.delete_business_domain(domain_id)
