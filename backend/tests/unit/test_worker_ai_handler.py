"""Unit tests for JobWorker._handle_ai_job.

The Azure SQL, Cosmos DB, Service Bus, and AI client are all mocked so
these tests run without any external infrastructure.
"""

from __future__ import annotations

import json
import uuid
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.ai.chains import GeneratedScript, QualityCheckResult, TestCase, TestStep
from app.ai.client import UsageRecord
from app.models.test_script import ScriptFormat


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_usage(tokens: int = 200) -> UsageRecord:
    return UsageRecord(
        model="gpt-4o",
        prompt_tokens=tokens // 2,
        completion_tokens=tokens // 2,
        total_tokens=tokens,
        latency_ms=300,
        cost_estimate_usd=0.003,
    )


def _make_test_cases() -> list[TestCase]:
    return [
        TestCase(
            test_case_id="TC-001",
            title="Login happy path",
            description="End-to-end login test",
            preconditions=["User account exists"],
            test_steps=[TestStep(1, "Navigate to /login", "Login page shown")],
            expected_outcome="Dashboard shown",
            priority="HIGH",
            test_type="positive",
        )
    ]


def _make_quality_result(verdict: str = "GOOD") -> QualityCheckResult:
    return QualityCheckResult(
        quality_score=80,
        improvement_suggestions=[],
        missing_information=[],
        testability_verdict=verdict,
        recommended_test_count=3,
    )


def _make_generated_script(fmt: ScriptFormat = ScriptFormat.PLAYWRIGHT_TS) -> GeneratedScript:
    return GeneratedScript(
        format=fmt,
        content="import { test } from '@playwright/test';\ntest('TC-001', async () => {});\n",
        test_case_count=1,
        usage=_make_usage(150),
    )


# ---------------------------------------------------------------------------
# Worker factory with mocked session
# ---------------------------------------------------------------------------


def _make_worker() -> Any:
    """Create a JobWorker instance with _playwright stubbed out."""
    from app.worker.service_bus_worker import JobWorker

    worker = JobWorker.__new__(JobWorker)
    worker._settings = MagicMock()
    worker._playwright = MagicMock()
    worker._running = True
    return worker


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_handle_ai_job_happy_path() -> None:
    """Full pipeline: quality check → test cases → script → Cosmos + SQL stored."""
    tenant_id = str(uuid.uuid4())
    job_id = str(uuid.uuid4())
    req_id = str(uuid.uuid4())
    project_id = uuid.uuid4()

    message = {
        "job_id": job_id,
        "tenant_id": tenant_id,
        "payload": {
            "requirement_ids": [req_id],
            "output_formats": ["playwright_ts"],
            "generation_config": {"include_assertions": True},
        },
    }

    worker = _make_worker()

    # Mock all async helper methods
    worker._update_job_status = AsyncMock()
    worker._load_requirements = AsyncMock(
        return_value=[
            {
                "id": req_id,
                "title": "User Login",
                "content": "Users must authenticate with email and password.",
                "business_domain": "AUTHENTICATION",
                "priority": "HIGH",
            }
        ]
    )
    worker._store_test_script_in_cosmos = AsyncMock(return_value=f"ts-gen-{job_id}-{req_id[:8]}")
    worker._create_test_script_row = AsyncMock()
    worker._mark_requirement_processed = AsyncMock()

    # Mock DB session for job + project fetch
    mock_job = MagicMock()
    mock_job.input_payload = json.dumps(message["payload"])
    mock_job.project_id = project_id

    mock_project = MagicMock()
    mock_project.base_url = "https://app.example.com"
    mock_project.system_type = MagicMock(value="WEB")
    mock_project.name = "Test Project"
    mock_project.settings = {"industry": "Healthcare"}

    mock_session = AsyncMock()
    mock_session.get = AsyncMock(side_effect=lambda model, pk: mock_job if "Job" in str(model) else mock_project)
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)

    mock_container = AsyncMock()
    mock_container.upsert_item = AsyncMock()

    with (
        patch("app.worker.service_bus_worker.get_session_factory") as mock_factory,
        patch("app.worker.service_bus_worker.set_tenant_context", new_callable=AsyncMock),
        patch("app.ai.chains.get_ai_client") as mock_get_client,
        patch("app.cosmos.get_tenant_container", return_value=mock_container),
    ):
        mock_factory.return_value = MagicMock(return_value=mock_session)

        mock_ai = MagicMock()
        mock_ai.complete_json = AsyncMock()
        mock_get_client.return_value = mock_ai

        with (
            patch(
                "app.worker.service_bus_worker.check_requirement_quality",
                new_callable=AsyncMock,
                return_value=(_make_quality_result("GOOD"), _make_usage()),
            ),
            patch(
                "app.worker.service_bus_worker.generate_test_cases_from_requirement",
                new_callable=AsyncMock,
                return_value=(_make_test_cases(), _make_usage()),
            ),
            patch(
                "app.worker.service_bus_worker.generate_script_from_test_cases",
                new_callable=AsyncMock,
                return_value=_make_generated_script(),
            ),
        ):
            await worker._handle_ai_job(message)

    # Job marked PROCESSING then COMPLETED
    calls = worker._update_job_status.call_args_list
    statuses = [c.args[2].value if hasattr(c.args[2], "value") else str(c.args[2]) for c in calls]
    assert "PROCESSING" in statuses
    assert "COMPLETED" in statuses

    # Script stored in Cosmos and SQL
    worker._store_test_script_in_cosmos.assert_awaited_once()
    worker._create_test_script_row.assert_awaited_once()
    worker._mark_requirement_processed.assert_awaited_once()


@pytest.mark.asyncio
async def test_handle_ai_job_untestable_requirement_skipped() -> None:
    """Requirements with UNTESTABLE verdict are skipped — no script created."""
    tenant_id = str(uuid.uuid4())
    job_id = str(uuid.uuid4())
    req_id = str(uuid.uuid4())
    project_id = uuid.uuid4()

    message = {
        "job_id": job_id,
        "tenant_id": tenant_id,
        "payload": {
            "requirement_ids": [req_id],
            "output_formats": ["playwright_ts"],
            "generation_config": {},
        },
    }

    worker = _make_worker()
    worker._update_job_status = AsyncMock()
    worker._load_requirements = AsyncMock(
        return_value=[
            {"id": req_id, "title": "TBD", "content": "TBD.", "business_domain": None, "priority": "LOW"}
        ]
    )
    worker._store_test_script_in_cosmos = AsyncMock()
    worker._create_test_script_row = AsyncMock()
    worker._mark_requirement_processed = AsyncMock()

    mock_job = MagicMock()
    mock_job.input_payload = json.dumps(message["payload"])
    mock_job.project_id = project_id
    mock_project = MagicMock()
    mock_project.base_url = None
    mock_project.system_type = MagicMock(value="WEB")
    mock_project.name = "P"
    mock_project.settings = None

    mock_session = AsyncMock()
    mock_session.get = AsyncMock(side_effect=lambda model, pk: mock_job if "Job" in str(model) else mock_project)
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)

    mock_container = AsyncMock()
    mock_container.upsert_item = AsyncMock()

    with (
        patch("app.worker.service_bus_worker.get_session_factory") as mock_factory,
        patch("app.worker.service_bus_worker.set_tenant_context", new_callable=AsyncMock),
        patch("app.cosmos.get_tenant_container", return_value=mock_container),
    ):
        mock_factory.return_value = MagicMock(return_value=mock_session)

        with (
            patch(
                "app.worker.service_bus_worker.check_requirement_quality",
                new_callable=AsyncMock,
                return_value=(_make_quality_result("UNTESTABLE"), _make_usage()),
            ),
            patch(
                "app.worker.service_bus_worker.generate_test_cases_from_requirement",
                new_callable=AsyncMock,
            ) as mock_gen,
        ):
            await worker._handle_ai_job(message)
            # Generation should NOT be called for untestable requirement
            mock_gen.assert_not_awaited()

    worker._store_test_script_in_cosmos.assert_not_awaited()


@pytest.mark.asyncio
async def test_handle_ai_job_no_requirements_fails_gracefully() -> None:
    """When requirement IDs don't resolve, job is marked FAILED without raising."""
    tenant_id = str(uuid.uuid4())
    job_id = str(uuid.uuid4())

    message = {
        "job_id": job_id,
        "tenant_id": tenant_id,
        "payload": {
            "requirement_ids": [str(uuid.uuid4())],
            "output_formats": ["playwright_ts"],
            "generation_config": {},
        },
    }

    worker = _make_worker()
    worker._update_job_status = AsyncMock()
    worker._load_requirements = AsyncMock(return_value=[])

    mock_job = MagicMock()
    mock_job.input_payload = json.dumps(message["payload"])
    mock_job.project_id = uuid.uuid4()
    mock_project = MagicMock()
    mock_project.base_url = None
    mock_project.system_type = MagicMock(value="WEB")
    mock_project.name = "P"
    mock_project.settings = None

    mock_session = AsyncMock()
    mock_session.get = AsyncMock(side_effect=lambda model, pk: mock_job if "Job" in str(model) else mock_project)
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)

    with (
        patch("app.worker.service_bus_worker.get_session_factory") as mock_factory,
        patch("app.worker.service_bus_worker.set_tenant_context", new_callable=AsyncMock),
    ):
        mock_factory.return_value = MagicMock(return_value=mock_session)
        await worker._handle_ai_job(message)

    calls = worker._update_job_status.call_args_list
    statuses = [str(c.args[2]) for c in calls]
    assert any("FAILED" in s for s in statuses)
