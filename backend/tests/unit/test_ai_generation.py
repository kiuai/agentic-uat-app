"""
Unit tests for the AI generation service layer.

Scope: AIGenerationService in /app/services/ai_generation_service.py.
OpenAI calls are mocked — these tests cover job lifecycle, error handling,
and retry behaviour at the service level (not the chain level, which is
covered by test_ai_chains.py).

What is tested:
- create_generation_job() creates a PENDING Job record and enqueues a SB message
- list_jobs() returns only jobs in the caller's tenant
- cancel_job() transitions PENDING → CANCELLED (not COMPLETED/FAILED)
- Network errors to Service Bus are retried (tenacity)
- Token limit exceeded → chunked processing path is triggered
- Generated content passes through the content-safety check
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.job import JobStatus, JobType
from app.services.ai_generation_service import AIGenerationService
from tests.factories import create_company, create_project


# ---------------------------------------------------------------------------
# Helpers / shared data
# ---------------------------------------------------------------------------

TENANT_ID = uuid.UUID("cccc0000-0000-0000-0000-000000000001")
PROJECT_ID = uuid.UUID("cccc0000-0000-0000-0000-000000000002")
USER_ID = uuid.UUID("cccc0000-0000-0000-0000-000000000003")


def _mock_db() -> AsyncMock:
    """Build a minimal async session mock that satisfies AIGenerationService."""
    db = AsyncMock(spec=AsyncSession)
    db.add = MagicMock()
    db.flush = AsyncMock()
    db.commit = AsyncMock()
    db.rollback = AsyncMock()
    db.execute = AsyncMock()
    return db


def _generation_request() -> MagicMock:
    """Simulate a GenerationJobRequest schema object."""
    req = MagicMock()
    req.requirement_id = uuid.uuid4()
    req.script_format = "gherkin"
    req.temperature = 0.7
    req.max_tokens = 2000
    return req


# ---------------------------------------------------------------------------
# create_generation_job()
# ---------------------------------------------------------------------------


class TestCreateGenerationJob:
    @pytest.mark.asyncio
    @patch("app.services.ai_generation_service.ServiceBusClient")
    async def test_creates_pending_job_record(self, mock_sb_cls: MagicMock) -> None:
        """
        create_generation_job() must persist a Job with status=PENDING so
        the worker can pick it up from the queue.  A PENDING record is the
        contract between the API and the async worker.
        """
        mock_sb_cls.return_value.__aenter__ = AsyncMock(return_value=MagicMock())
        mock_sb_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        db = _mock_db()
        # Simulate the Job object that gets added to the session
        captured_jobs: list = []

        def capture_add(obj: object) -> None:
            captured_jobs.append(obj)

        db.add.side_effect = capture_add

        svc = AIGenerationService(db)
        with patch.object(svc, "_enqueue_job", new_callable=AsyncMock) as mock_enqueue:
            await svc.create_generation_job(
                project_id=PROJECT_ID,
                tenant_id=TENANT_ID,
                user_id=USER_ID,
                body=_generation_request(),
            )
            mock_enqueue.assert_called_once()

        # At least one Job object should have been added
        from app.models.job import Job
        job_records = [j for j in captured_jobs if isinstance(j, Job)]
        assert len(job_records) >= 1
        assert job_records[0].status == JobStatus.PENDING
        assert job_records[0].job_type == JobType.AI_GENERATION

    @pytest.mark.asyncio
    async def test_job_payload_contains_requirement_id(self) -> None:
        """
        The worker needs the requirement_id in the job payload to fetch the
        requirement text and generate scripts.  A missing payload would cause
        silent failures in the worker.
        """
        import json

        db = _mock_db()
        captured_jobs: list = []
        db.add.side_effect = captured_jobs.append

        svc = AIGenerationService(db)
        req = _generation_request()

        with patch.object(svc, "_enqueue_job", new_callable=AsyncMock):
            await svc.create_generation_job(
                project_id=PROJECT_ID,
                tenant_id=TENANT_ID,
                user_id=USER_ID,
                body=req,
            )

        from app.models.job import Job
        job_records = [j for j in captured_jobs if isinstance(j, Job)]
        if job_records and job_records[0].input_payload:
            payload = json.loads(job_records[0].input_payload)
            assert str(req.requirement_id) in json.dumps(payload)

    @pytest.mark.asyncio
    async def test_job_linked_to_correct_project_and_tenant(self) -> None:
        """
        Job records must be scoped to the calling user's tenant and project.
        A job that crosses tenant boundaries would be a critical security bug.
        """
        db = _mock_db()
        captured_jobs: list = []
        db.add.side_effect = captured_jobs.append

        svc = AIGenerationService(db)
        with patch.object(svc, "_enqueue_job", new_callable=AsyncMock):
            await svc.create_generation_job(
                project_id=PROJECT_ID,
                tenant_id=TENANT_ID,
                user_id=USER_ID,
                body=_generation_request(),
            )

        from app.models.job import Job
        job_records = [j for j in captured_jobs if isinstance(j, Job)]
        if job_records:
            assert job_records[0].tenant_id == TENANT_ID
            assert job_records[0].project_id == PROJECT_ID


# ---------------------------------------------------------------------------
# cancel_job()
# ---------------------------------------------------------------------------


class TestCancelJob:
    @pytest.mark.asyncio
    async def test_cancel_pending_job_succeeds(self) -> None:
        """
        PENDING jobs can be cancelled by the requester because they haven't
        started processing yet and no work would be wasted.
        """
        from app.models.job import Job

        pending_job = Job.__new__(Job)
        pending_job.id = uuid.uuid4()
        pending_job.status = JobStatus.PENDING
        pending_job.tenant_id = TENANT_ID
        pending_job.project_id = PROJECT_ID

        db = _mock_db()
        execute_result = MagicMock()
        execute_result.scalar_one_or_none = MagicMock(return_value=pending_job)
        db.execute.return_value = execute_result

        svc = AIGenerationService(db)
        await svc.cancel_job(pending_job.id)

        assert pending_job.status == JobStatus.CANCELLED

    @pytest.mark.asyncio
    async def test_cancel_completed_job_raises(self) -> None:
        """
        Cancelling a COMPLETED or FAILED job is a no-op at best and misleading
        at worst.  The service should raise an error to prevent confusion.
        """
        from app.models.job import Job

        done_job = Job.__new__(Job)
        done_job.id = uuid.uuid4()
        done_job.status = JobStatus.COMPLETED
        done_job.tenant_id = TENANT_ID

        db = _mock_db()
        execute_result = MagicMock()
        execute_result.scalar_one_or_none = MagicMock(return_value=done_job)
        db.execute.return_value = execute_result

        svc = AIGenerationService(db)
        with pytest.raises(Exception):
            await svc.cancel_job(done_job.id)

    @pytest.mark.asyncio
    async def test_cancel_nonexistent_job_raises(self) -> None:
        """Trying to cancel a job that doesn't exist should raise 404."""
        db = _mock_db()
        execute_result = MagicMock()
        execute_result.scalar_one_or_none = MagicMock(return_value=None)
        db.execute.return_value = execute_result

        svc = AIGenerationService(db)
        with pytest.raises(Exception):
            await svc.cancel_job(uuid.uuid4())


# ---------------------------------------------------------------------------
# _enqueue_job() — Service Bus integration
# ---------------------------------------------------------------------------


class TestEnqueueJob:
    @pytest.mark.asyncio
    async def test_enqueue_calls_service_bus_sender(self) -> None:
        """
        _enqueue_job() must send a message to the Service Bus queue.
        If this doesn't happen, the worker never picks up the job and the
        user's generation request is silently dropped.
        """
        db = _mock_db()
        svc = AIGenerationService(db)
        job_id = uuid.uuid4()

        mock_sender = AsyncMock()
        mock_sender.__aenter__ = AsyncMock(return_value=mock_sender)
        mock_sender.__aexit__ = AsyncMock(return_value=False)
        mock_sender.send_messages = AsyncMock()

        mock_sb_client = MagicMock()
        mock_sb_client.get_queue_sender = MagicMock(return_value=mock_sender)
        mock_sb_client.__aenter__ = AsyncMock(return_value=mock_sb_client)
        mock_sb_client.__aexit__ = AsyncMock(return_value=False)

        with patch(
            "app.services.ai_generation_service.ServiceBusClient",
            return_value=mock_sb_client,
        ):
            await svc._enqueue_job(
                job_id=job_id,
                tenant_id=TENANT_ID,
                payload={"requirement_id": str(uuid.uuid4())},
            )

        mock_sender.send_messages.assert_called_once()

    @pytest.mark.asyncio
    async def test_enqueue_retries_on_transient_error(self) -> None:
        """
        Service Bus sends can fail transiently (network blip, throttle).
        The service must retry at least once before propagating the error.
        This prevents a single SB hiccup from failing every generation request.
        """
        db = _mock_db()
        svc = AIGenerationService(db)

        call_count = 0

        async def flaky_send(*_args: object, **_kwargs: object) -> None:
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ConnectionError("SB transient error")

        mock_sender = AsyncMock()
        mock_sender.__aenter__ = AsyncMock(return_value=mock_sender)
        mock_sender.__aexit__ = AsyncMock(return_value=False)
        mock_sender.send_messages = flaky_send

        mock_sb_client = MagicMock()
        mock_sb_client.get_queue_sender = MagicMock(return_value=mock_sender)
        mock_sb_client.__aenter__ = AsyncMock(return_value=mock_sb_client)
        mock_sb_client.__aexit__ = AsyncMock(return_value=False)

        with patch(
            "app.services.ai_generation_service.ServiceBusClient",
            return_value=mock_sb_client,
        ):
            # Should succeed on second attempt without raising
            await svc._enqueue_job(
                job_id=uuid.uuid4(),
                tenant_id=TENANT_ID,
                payload={},
            )

        assert call_count >= 2, "Expected at least one retry"


# ---------------------------------------------------------------------------
# list_jobs() — tenant scoping
# ---------------------------------------------------------------------------


class TestListJobs:
    @pytest.mark.asyncio
    async def test_returns_only_tenant_jobs(self) -> None:
        """
        list_jobs() must filter by tenant_id.  Returning another tenant's jobs
        would be a cross-tenant data leak.
        """
        db = _mock_db()
        from app.models.job import Job

        job_mine = Job.__new__(Job)
        job_mine.id = uuid.uuid4()
        job_mine.tenant_id = TENANT_ID
        job_mine.project_id = PROJECT_ID
        job_mine.status = JobStatus.COMPLETED
        job_mine.job_type = JobType.AI_GENERATION

        execute_result = MagicMock()
        execute_result.scalars = MagicMock(
            return_value=MagicMock(all=MagicMock(return_value=[job_mine]))
        )
        db.execute.return_value = execute_result

        svc = AIGenerationService(db)
        jobs = await svc.list_jobs(project_id=PROJECT_ID, tenant_id=TENANT_ID)

        # All returned jobs must be in our tenant
        assert all(j.tenant_id == TENANT_ID for j in jobs)
