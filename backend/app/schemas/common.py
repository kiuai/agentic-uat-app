"""Shared Pydantic schema types."""

from __future__ import annotations

from typing import Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class PaginationMeta(BaseModel):
    total: int
    limit: int
    has_more: bool
    next_cursor: str | None = None


class PaginatedResponse(BaseModel, Generic[T]):
    data: list[T]
    pagination: PaginationMeta = Field(alias="_pagination")

    model_config = {"populate_by_name": True}


class ErrorDetail(BaseModel):
    type: str
    title: str
    status: int
    detail: str
    instance: str | None = None
    request_id: str | None = None


class Links(BaseModel):
    self: str | None = None
    related: dict[str, str] = {}
