"""Pydantic v2 schemas for Enterprise, Company, and BusinessDomain."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Enterprise
# ---------------------------------------------------------------------------


class EnterpriseBase(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    slug: str = Field(min_length=1, max_length=100, pattern=r"^[a-z0-9-]+$")
    azure_ad_tenant_id: str | None = Field(None, max_length=255)
    settings: dict[str, Any] | None = None
    is_active: bool = True


class EnterpriseCreate(EnterpriseBase):
    pass


class EnterpriseUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=255)
    azure_ad_tenant_id: str | None = None
    settings: dict[str, Any] | None = None
    is_active: bool | None = None


class EnterpriseResponse(EnterpriseBase):
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Company
# ---------------------------------------------------------------------------


class CompanyBase(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    slug: str = Field(min_length=1, max_length=100, pattern=r"^[a-z0-9-]+$")
    settings: dict[str, Any] | None = None
    is_active: bool = True


class CompanyCreate(CompanyBase):
    enterprise_id: uuid.UUID


class CompanyUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=255)
    settings: dict[str, Any] | None = None
    is_active: bool | None = None


class CompanyResponse(CompanyBase):
    id: uuid.UUID
    enterprise_id: uuid.UUID
    tenant_id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# BusinessDomain
# ---------------------------------------------------------------------------


class BusinessDomainBase(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    code: str = Field(min_length=1, max_length=100, pattern=r"^[A-Z0-9_]+$")
    description: str | None = Field(None, max_length=1000)
    is_active: bool = True


class BusinessDomainCreate(BusinessDomainBase):
    pass


class BusinessDomainUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = None
    is_active: bool | None = None


class BusinessDomainResponse(BusinessDomainBase):
    id: uuid.UUID
    tenant_id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# Thin read aliases for code that imported the old names
EnterpriseRead = EnterpriseResponse
CompanyRead = CompanyResponse
