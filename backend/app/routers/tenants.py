"""Tenant management endpoints (Global and Enterprise Admins)."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status

from app.dependencies import CurrentUser, TenantDB, require_roles
from app.models.user import UserRole
from app.schemas.tenant import CompanyCreate, CompanyRead, EnterpriseCreate, EnterpriseRead
from app.services.tenant_service import TenantService

router = APIRouter(prefix="/admin")


@router.get(
    "/enterprises",
    response_model=list[EnterpriseRead],
    dependencies=[Depends(require_roles(UserRole.GLOBAL_ADMIN))],
)
async def list_enterprises(db: TenantDB) -> list[EnterpriseRead]:
    service = TenantService(db)
    return await service.list_enterprises()


@router.post(
    "/enterprises",
    response_model=EnterpriseRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_roles(UserRole.GLOBAL_ADMIN))],
)
async def create_enterprise(body: EnterpriseCreate, db: TenantDB) -> EnterpriseRead:
    service = TenantService(db)
    return await service.create_enterprise(body)


@router.get(
    "/enterprises/{enterprise_id}/companies",
    response_model=list[CompanyRead],
    dependencies=[Depends(require_roles(UserRole.GLOBAL_ADMIN, UserRole.ENTERPRISE_ADMIN))],
)
async def list_companies(enterprise_id: uuid.UUID, db: TenantDB) -> list[CompanyRead]:
    service = TenantService(db)
    return await service.list_companies(enterprise_id)


@router.post(
    "/enterprises/{enterprise_id}/companies",
    response_model=CompanyRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_roles(UserRole.GLOBAL_ADMIN, UserRole.ENTERPRISE_ADMIN))],
)
async def create_company(
    enterprise_id: uuid.UUID, body: CompanyCreate, db: TenantDB
) -> CompanyRead:
    service = TenantService(db)
    return await service.create_company(enterprise_id, body)
