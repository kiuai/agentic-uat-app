"""
Export orchestration service.

Coordinates the full export pipeline:
  1. Load TestScript SQL metadata (enforces tenant isolation via RLS session)
  2. Fetch Cosmos DB document to obtain pre-generated script content or raw
     test-case JSON for re-generation
  3. Instantiate the correct exporter and run export()
  4. Validate generated output with exporter.validate_output()
  5. Upload to Azure Blob Storage at:
       tenant-{tenant_id}/exports/{script_id}/{format}.{ext}
  6. Return ExportResult with a 1-hour SAS download URL

Bulk and cycle exports follow the same pipeline but zip the outputs.
"""

from __future__ import annotations

import io
import json
import uuid
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import structlog
from azure.cosmos.aio import ContainerProxy
from azure.cosmos.exceptions import CosmosResourceNotFoundError
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.exporters.base import (
    ExportContext,
    ExportFormat,
    TestCase,
    ValidationResult,
)
from app.exporters.gherkin_exporter import GherkinExporter
from app.exporters.playwright_exporter import PlaywrightExporter
from app.exporters.pytest_exporter import PytestExporter
from app.exporters.robot_framework_exporter import RobotFrameworkExporter
from app.exporters.selenium_exporter import SeleniumExporter
from app.models.test_cycle import TestAssignment
from app.models.test_script import ScriptFormat, ScriptStatus, TestScript
from app.services.blob_service import BlobService

logger = structlog.get_logger(__name__)

# Map ScriptFormat → ExportFormat (they share values)
_FORMAT_MAP: dict[ScriptFormat, ExportFormat] = {
    ScriptFormat.PLAYWRIGHT_TS: ExportFormat.PLAYWRIGHT_TS,
    ScriptFormat.PLAYWRIGHT_JS: ExportFormat.PLAYWRIGHT_JS,
    ScriptFormat.SELENIUM_PYTHON: ExportFormat.SELENIUM_PYTHON,
    ScriptFormat.PYTEST: ExportFormat.PYTEST,
    ScriptFormat.ROBOT_FRAMEWORK: ExportFormat.ROBOT_FRAMEWORK,
    ScriptFormat.GHERKIN: ExportFormat.GHERKIN,
}


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------


@dataclass
class ExportResult:
    script_id: uuid.UUID
    format: ExportFormat
    file_name: str
    content: str
    blob_uri: str | None
    download_url: str | None   # SAS URL, 1-hour expiry
    expires_at: datetime | None
    validation: ValidationResult
    generated_at: datetime


@dataclass
class BulkExportResult:
    script_ids: list[uuid.UUID]
    format: ExportFormat
    blob_uri: str | None
    download_url: str | None
    expires_at: datetime | None
    file_count: int
    generated_at: datetime


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class ExportService:
    """
    Orchestrates multi-format test script exports.

    Constructor accepts an AsyncSession (for SQL) and a Cosmos ContainerProxy
    (for script content).  Both are required for full operation; the service
    degrades gracefully when blob upload is unavailable.
    """

    def __init__(self, db: AsyncSession, cosmos: ContainerProxy) -> None:
        self._db = db
        self._cosmos = cosmos
        self._blob = BlobService()

    # ── Public API ────────────────────────────────────────────────────────

    async def export_test_script(
        self,
        test_script_id: uuid.UUID,
        export_format: ExportFormat,
        tenant_id: uuid.UUID,
        project_name: str = "KAATS",
        system_url: str = "",
    ) -> ExportResult:
        """
        Export a single test script to the requested format.

        1. Load TestScript SQL row (RLS enforces tenant isolation)
        2. Fetch Cosmos doc to get content or test-case JSON
        3. Instantiate exporter, run export(), validate
        4. Upload to Blob, generate SAS URL (1-hour)
        5. Return ExportResult
        """
        script = await self._load_script(test_script_id)
        cosmos_doc = await self._fetch_cosmos_doc(script)

        ctx = ExportContext(
            project_name=project_name,
            system_url=system_url or "",
            export_format=export_format,
        )
        exporter = self._make_exporter(export_format, ctx)

        # Prefer pre-generated content in the Cosmos doc; fall back to re-generation
        content = self._get_pregenerated_content(cosmos_doc, export_format)
        if not content:
            test_cases = self._parse_test_cases(cosmos_doc)
            content = exporter.export(test_cases)

        validation = exporter.validate_output(content)
        if not validation.is_valid:
            logger.warning(
                "export_validation_failed",
                script_id=str(test_script_id),
                format=export_format.value,
                errors=validation.errors,
            )

        file_name = f"{_safe_name(script.title)}{exporter.get_file_extension()}"
        blob_path = (
            f"exports/{test_script_id}/{export_format.value}{exporter.get_file_extension()}"
        )
        blob_uri, download_url, expires_at = await self._upload_and_sign(
            tenant_id, blob_path, content.encode("utf-8"),
            _mime_for_format(export_format),
        )

        logger.info(
            "export_completed",
            script_id=str(test_script_id),
            format=export_format.value,
            valid=validation.is_valid,
        )
        return ExportResult(
            script_id=test_script_id,
            format=export_format,
            file_name=file_name,
            content=content,
            blob_uri=blob_uri,
            download_url=download_url,
            expires_at=expires_at,
            validation=validation,
            generated_at=datetime.now(timezone.utc),
        )

    async def export_bulk(
        self,
        test_script_ids: list[uuid.UUID],
        export_format: ExportFormat,
        tenant_id: uuid.UUID,
        project_name: str = "KAATS",
        system_url: str = "",
    ) -> BulkExportResult:
        """
        Export multiple scripts and return them as a single ZIP archive.
        """
        zip_buffer = io.BytesIO()
        file_count = 0

        with zipfile.ZipFile(zip_buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
            for script_id in test_script_ids:
                try:
                    result = await self.export_test_script(
                        script_id, export_format, tenant_id, project_name, system_url
                    )
                    zf.writestr(result.file_name, result.content)
                    file_count += 1
                except Exception as exc:
                    logger.warning(
                        "bulk_export_script_failed",
                        script_id=str(script_id),
                        error=str(exc),
                    )
                    zf.writestr(
                        f"ERROR_{script_id}.txt",
                        f"Export failed: {exc}",
                    )

        zip_bytes = zip_buffer.getvalue()
        blob_path = (
            f"exports/bulk/{uuid.uuid4()}/{export_format.value}_scripts.zip"
        )
        blob_uri, download_url, expires_at = await self._upload_and_sign(
            tenant_id, blob_path, zip_bytes, "application/zip"
        )

        return BulkExportResult(
            script_ids=test_script_ids,
            format=export_format,
            blob_uri=blob_uri,
            download_url=download_url,
            expires_at=expires_at,
            file_count=file_count,
            generated_at=datetime.now(timezone.utc),
        )

    async def export_test_cycle(
        self,
        test_cycle_id: uuid.UUID,
        export_format: ExportFormat,
        tenant_id: uuid.UUID,
        project_name: str = "KAATS",
        system_url: str = "",
    ) -> BulkExportResult:
        """
        Export all APPROVED scripts assigned in a test cycle as a ZIP archive.
        """
        # Load all assignments in the cycle
        result = await self._db.execute(
            select(TestAssignment)
            .where(TestAssignment.cycle_id == test_cycle_id)
        )
        assignments = result.scalars().all()

        # Collect unique script IDs
        script_ids = list({a.script_id for a in assignments})

        # Filter to only APPROVED scripts
        approved_ids: list[uuid.UUID] = []
        for sid in script_ids:
            script = await self._db.get(TestScript, sid)
            if script and script.status == ScriptStatus.APPROVED:
                approved_ids.append(sid)

        if not approved_ids:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No approved scripts found in this test cycle.",
            )

        return await self.export_bulk(
            approved_ids, export_format, tenant_id, project_name, system_url
        )

    # ── Private helpers ───────────────────────────────────────────────────

    async def _load_script(self, script_id: uuid.UUID) -> TestScript:
        script = await self._db.get(TestScript, script_id)
        if not script:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Test script not found.",
            )
        return script

    async def _fetch_cosmos_doc(self, script: TestScript) -> dict[str, Any]:
        if not script.cosmos_doc_id:
            # No Cosmos doc — return a minimal stub
            return {
                "id": str(script.id),
                "title": script.title,
                "description": script.description or "",
                "scripts": {},
                "test_cases": [],
            }
        try:
            return await self._cosmos.read_item(
                item=script.cosmos_doc_id,
                partition_key=str(script.project_id),
            )
        except CosmosResourceNotFoundError:
            logger.warning(
                "cosmos_doc_not_found",
                script_id=str(script.id),
                cosmos_doc_id=script.cosmos_doc_id,
            )
            return {
                "id": script.cosmos_doc_id,
                "title": script.title,
                "description": script.description or "",
                "scripts": {},
                "test_cases": [],
            }

    @staticmethod
    def _get_pregenerated_content(
        doc: dict[str, Any], export_format: ExportFormat
    ) -> str | None:
        """Return pre-generated script string if already in the Cosmos doc."""
        scripts = doc.get("scripts", {})
        return scripts.get(export_format.value) or None

    @staticmethod
    def _parse_test_cases(doc: dict[str, Any]) -> list[TestCase]:
        """
        Parse test case structures from a Cosmos document.

        Supports two document layouts:
          1. ``test_cases`` key → list[dict] — structured AI output
          2. Fallback — synthesise a single TestCase from the document title/description
        """
        raw = doc.get("test_cases", [])
        if raw:
            from app.exporters.base import BaseExporter
            dummy_ctx = ExportContext(
                project_name="", system_url="", export_format=ExportFormat.PLAYWRIGHT_TS
            )

            class _Parser(BaseExporter):
                def export(self, _): return ""
                def get_file_extension(self): return ""

            parser = _Parser(dummy_ctx)
            return [parser._dict_to_test_case(item) for item in raw]

        # Fallback: create a single TestCase from doc metadata
        return [
            TestCase(
                id=doc.get("id", ""),
                title=doc.get("title", "Test Case"),
                description=doc.get("description", ""),
                preconditions=[],
                steps=[],
                expected_outcome=doc.get("expected_outcome", ""),
            )
        ]

    def _make_exporter(self, fmt: ExportFormat, ctx: ExportContext):
        if fmt == ExportFormat.PLAYWRIGHT_TS:
            return PlaywrightExporter(ctx, language="ts")
        if fmt == ExportFormat.PLAYWRIGHT_JS:
            return PlaywrightExporter(ctx, language="js")
        if fmt == ExportFormat.SELENIUM_PYTHON:
            return SeleniumExporter(ctx)
        if fmt == ExportFormat.PYTEST:
            return PytestExporter(ctx)
        if fmt == ExportFormat.ROBOT_FRAMEWORK:
            return RobotFrameworkExporter(ctx)
        if fmt == ExportFormat.GHERKIN:
            return GherkinExporter(ctx)
        raise ValueError(f"No exporter for format: {fmt}")

    async def _upload_and_sign(
        self,
        tenant_id: uuid.UUID,
        blob_path: str,
        data: bytes,
        content_type: str,
    ) -> tuple[str | None, str | None, datetime | None]:
        """Upload to Blob and return (blob_uri, sas_url, expires_at). Never raises."""
        try:
            from datetime import timedelta
            blob_uri = await self._blob.upload(tenant_id, blob_path, data, content_type)
            download_url = self._blob.get_sas_url(tenant_id, blob_path, expiry_hours=1)
            expires_at = datetime.now(timezone.utc) + timedelta(hours=1)
            return blob_uri, download_url, expires_at
        except Exception as exc:
            logger.warning("export_blob_upload_failed", path=blob_path, error=str(exc))
            return None, None, None


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------


def _safe_name(title: str) -> str:
    """Return a filesystem-safe version of a test script title."""
    import re
    safe = re.sub(r"[^\w\s-]", "", title)
    safe = re.sub(r"[\s_-]+", "_", safe).strip("_")
    return safe[:80] or "test_script"


def _mime_for_format(fmt: ExportFormat) -> str:
    return {
        ExportFormat.PLAYWRIGHT_TS: "application/typescript",
        ExportFormat.PLAYWRIGHT_JS: "application/javascript",
        ExportFormat.SELENIUM_PYTHON: "text/x-python",
        ExportFormat.PYTEST: "text/x-python",
        ExportFormat.ROBOT_FRAMEWORK: "text/plain",
        ExportFormat.GHERKIN: "text/plain",
    }.get(fmt, "text/plain")
