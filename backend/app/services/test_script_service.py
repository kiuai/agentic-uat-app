"""Test script service — Cosmos DB document operations."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException, status

import structlog
from azure.cosmos.aio import ContainerProxy
from azure.cosmos.exceptions import CosmosResourceNotFoundError

from app.middleware.rbac import assert_domain_access
from app.models.test_script import ScriptStatus
from app.models.user import User
from app.schemas.test_script import (
    ExportRequest, ExportResponse,
    TestScriptCreate, TestScriptRead, TestScriptUpdate,
)

logger = structlog.get_logger(__name__)


def _doc_to_read(doc: dict[str, Any]) -> TestScriptRead:
    return TestScriptRead(
        id=doc["id"],
        project_id=uuid.UUID(doc["project_id"]),
        tenant_id=uuid.UUID(doc["tenant_id"]),
        title=doc["title"],
        description=doc.get("description"),
        status=ScriptStatus(doc["status"]),
        version=doc.get("version", 1),
        tags=doc.get("tags", []),
        domain_code=doc.get("domain_code"),
        source_job_id=uuid.UUID(doc["source_job_id"]) if doc.get("source_job_id") else None,
        requirement_ids=[uuid.UUID(r) for r in doc.get("requirement_ids", [])],
        scripts=doc.get("scripts", {}),
        created_at=datetime.fromisoformat(doc["created_at"]),
        updated_at=datetime.fromisoformat(doc["updated_at"]),
        created_by=uuid.UUID(doc["created_by"]),
        approved_by=uuid.UUID(doc["approved_by"]) if doc.get("approved_by") else None,
        approved_at=datetime.fromisoformat(doc["approved_at"]) if doc.get("approved_at") else None,
    )


class TestScriptService:
    def __init__(self, container: ContainerProxy) -> None:
        self._container = container

    async def list_scripts(
        self,
        project_id: uuid.UUID,
        user: User,
        status_filter: str | None = None,
        domain_code: str | None = None,
    ) -> list[TestScriptRead]:
        query = "SELECT * FROM c WHERE c.type = 'test_script' AND c.project_id = @project_id"
        params: list[dict[str, Any]] = [{"name": "@project_id", "value": str(project_id)}]

        if status_filter:
            query += " AND c.status = @status"
            params.append({"name": "@status", "value": status_filter})

        if domain_code:
            query += " AND c.domain_code = @domain_code"
            params.append({"name": "@domain_code", "value": domain_code})

        items = [
            item async for item in self._container.query_items(
                query=query, parameters=params
            )
        ]
        scripts = [_doc_to_read(item) for item in items]

        # BPO: filter to domain
        from app.models.user import UserRole
        if user.role == UserRole.BUSINESS_PROCESS_OWNER:
            user_domains = user.get_domains()
            scripts = [s for s in scripts if s.domain_code in user_domains]

        return scripts

    async def create_script(
        self,
        project_id: uuid.UUID,
        tenant_id: uuid.UUID,
        user_id: uuid.UUID,
        body: TestScriptCreate,
    ) -> TestScriptRead:
        now = datetime.now(timezone.utc).isoformat()
        doc: dict[str, Any] = {
            "id": f"ts-{uuid.uuid4()}",
            "schema_version": 1,
            "type": "test_script",
            "project_id": str(project_id),
            "tenant_id": str(tenant_id),
            "title": body.title,
            "description": body.description,
            "status": ScriptStatus.DRAFT.value,
            "version": 1,
            "version_history": [],
            "tags": body.tags,
            "domain_code": body.domain_code,
            "source_job_id": None,
            "requirement_ids": [str(r) for r in body.requirement_ids],
            "scripts": {k.value: v for k, v in body.scripts.items()},
            "created_at": now,
            "updated_at": now,
            "created_by": str(user_id),
            "approved_by": None,
            "approved_at": None,
        }
        await self._container.create_item(doc)
        logger.info("test_script_created", script_id=doc["id"], project_id=str(project_id))
        return _doc_to_read(doc)

    async def get_script(
        self, script_id: str, project_id: str, user: User
    ) -> TestScriptRead:
        try:
            doc = await self._container.read_item(item=script_id, partition_key=project_id)
        except CosmosResourceNotFoundError:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Script not found.")
        script = _doc_to_read(doc)
        assert_domain_access(user, script.domain_code)
        return script

    async def update_script(
        self, script_id: str, project_id: str, body: TestScriptUpdate, user: User
    ) -> TestScriptRead:
        try:
            doc = await self._container.read_item(item=script_id, partition_key=project_id)
        except CosmosResourceNotFoundError:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Script not found.")

        if doc["status"] == ScriptStatus.LOCKED.value:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="LOCKED scripts cannot be edited. Create a new version.",
            )
        if body.title is not None:
            doc["title"] = body.title
        if body.description is not None:
            doc["description"] = body.description
        if body.tags is not None:
            doc["tags"] = body.tags
        if body.domain_code is not None:
            doc["domain_code"] = body.domain_code
        if body.scripts is not None:
            doc["scripts"] = {k.value: v for k, v in body.scripts.items()}
            doc["version"] = doc.get("version", 1) + 1

        doc["updated_at"] = datetime.now(timezone.utc).isoformat()
        await self._container.replace_item(item=script_id, body=doc)
        return _doc_to_read(doc)

    async def delete_script(self, script_id: str, project_id: str) -> None:
        try:
            await self._container.delete_item(item=script_id, partition_key=project_id)
        except CosmosResourceNotFoundError:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Script not found.")

    async def submit_for_review(
        self, script_id: str, project_id: str, user: User
    ) -> TestScriptRead:
        doc = await self._container.read_item(item=script_id, partition_key=project_id)
        if doc["status"] != ScriptStatus.DRAFT.value:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Only DRAFT scripts can be submitted. Current status: {doc['status']}",
            )
        doc["status"] = ScriptStatus.IN_REVIEW.value
        doc["updated_at"] = datetime.now(timezone.utc).isoformat()
        await self._container.replace_item(item=script_id, body=doc)
        return _doc_to_read(doc)

    async def approve_script(
        self, script_id: str, project_id: str, user: User, comments: str | None
    ) -> TestScriptRead:
        doc = await self._container.read_item(item=script_id, partition_key=project_id)
        if doc["status"] != ScriptStatus.IN_REVIEW.value:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Only IN_REVIEW scripts can be approved. Current status: {doc['status']}",
            )
        now = datetime.now(timezone.utc).isoformat()
        doc["status"] = ScriptStatus.APPROVED.value
        doc["approved_by"] = str(user.id)
        doc["approved_at"] = now
        doc["updated_at"] = now
        await self._container.replace_item(item=script_id, body=doc)
        return _doc_to_read(doc)

    async def reject_script(
        self, script_id: str, project_id: str, user: User, comments: str
    ) -> TestScriptRead:
        doc = await self._container.read_item(item=script_id, partition_key=project_id)
        if doc["status"] != ScriptStatus.IN_REVIEW.value:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Only IN_REVIEW scripts can be rejected. Current status: {doc['status']}",
            )
        doc["status"] = ScriptStatus.REJECTED.value
        doc["rejection_comments"] = comments
        doc["updated_at"] = datetime.now(timezone.utc).isoformat()
        await self._container.replace_item(item=script_id, body=doc)
        return _doc_to_read(doc)

    async def export_script(
        self, script_id: str, project_id: str, body: ExportRequest
    ) -> ExportResponse:
        doc = await self._container.read_item(item=script_id, partition_key=project_id)
        scripts = doc.get("scripts", {})
        content = scripts.get(body.format.value)
        if content is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Format '{body.format.value}' not available for this script.",
            )
        return ExportResponse(format=body.format, content=content)
