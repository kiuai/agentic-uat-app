"""
Crawler job service — creates CrawlJob records and dispatches to Service Bus.

The API layer calls start_crawl_job() which writes a PENDING CrawlJob row
and publishes to the crawl-jobs Service Bus topic.

The worker calls process_crawl_job() which runs the Playwright crawler,
persists CrawlPage rows, optionally triggers AI script generation, and
transitions the job to COMPLETED / FAILED.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any

import structlog
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.crawl_job import CrawlAuthType, CrawlJob, CrawlJobStatus, CrawlPage, CrawlerType
from app.schemas.crawl_job import CrawlJobCreate, CrawlJobResponse, CrawlPageResponse
from app.services.servicebus_service import ServiceBusService

logger = structlog.get_logger(__name__)


class CrawlerService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    # ── Job lifecycle ─────────────────────────────────────────────────────

    async def start_crawl_job(
        self,
        project_id: uuid.UUID,
        tenant_id: uuid.UUID,
        user_id: uuid.UUID,
        body: CrawlJobCreate,
    ) -> CrawlJobResponse:
        """
        Create a CrawlJob record (status=PENDING) and publish to Service Bus.
        Returns immediately — client polls status via get_job().
        """
        if body.crawler_type == CrawlerType.WEB and not body.target_url:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="target_url is required for WEB crawler.",
            )
        if body.crawler_type == CrawlerType.SAP_FIORI and not body.launchpad_url:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="launchpad_url is required for SAP_FIORI crawler.",
            )

        job = CrawlJob(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            project_id=project_id,
            crawler_type=body.crawler_type,
            status=CrawlJobStatus.PENDING,
            target_url=body.target_url,
            launchpad_url=body.launchpad_url,
            max_pages=body.max_pages,
            auth_type=body.auth_type,
            generate_scripts=body.generate_scripts,
            created_by=user_id,
        )
        self._db.add(job)
        await self._db.flush()
        await self._db.refresh(job)

        # Publish to Service Bus
        payload: dict[str, Any] = {
            "crawler_type": body.crawler_type.value,
            "target_url": body.target_url,
            "launchpad_url": body.launchpad_url,
            "max_pages": body.max_pages,
            "auth_type": body.auth_type.value,
            "generate_scripts": body.generate_scripts,
        }
        await ServiceBusService().publish_crawl_job(
            job_id=str(job.id),
            tenant_id=str(tenant_id),
            payload=payload,
        )

        logger.info(
            "crawl_job_created",
            job_id=str(job.id),
            crawler_type=body.crawler_type.value,
            tenant_id=str(tenant_id),
        )
        return CrawlJobResponse.model_validate(job)

    async def list_jobs(
        self, project_id: uuid.UUID, tenant_id: uuid.UUID
    ) -> list[CrawlJobResponse]:
        result = await self._db.execute(
            select(CrawlJob)
            .where(CrawlJob.project_id == project_id, CrawlJob.tenant_id == tenant_id)
            .order_by(CrawlJob.created_at.desc())
        )
        return [CrawlJobResponse.model_validate(j) for j in result.scalars()]

    async def get_job(self, job_id: uuid.UUID) -> CrawlJobResponse:
        job = await self._db.get(CrawlJob, job_id)
        if not job:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Crawl job not found."
            )
        return CrawlJobResponse.model_validate(job)

    async def cancel_job(
        self, job_id: uuid.UUID, tenant_id: uuid.UUID
    ) -> CrawlJobResponse:
        job = await self._db.get(CrawlJob, job_id)
        if not job:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Crawl job not found."
            )
        if job.tenant_id != tenant_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)
        if job.status not in (CrawlJobStatus.PENDING, CrawlJobStatus.PROCESSING):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Cannot cancel job in status '{job.status.value}'.",
            )
        job.status = CrawlJobStatus.CANCELLED
        job.completed_at = datetime.now(timezone.utc)
        await self._db.flush()
        return CrawlJobResponse.model_validate(job)

    # ── Results ───────────────────────────────────────────────────────────

    async def get_crawl_results(
        self, job_id: uuid.UUID, tenant_id: uuid.UUID
    ) -> list[CrawlPageResponse]:
        """Return all CrawlPage records for a completed job."""
        job = await self._db.get(CrawlJob, job_id)
        if not job:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Crawl job not found."
            )
        if job.tenant_id != tenant_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)

        result = await self._db.execute(
            select(CrawlPage)
            .where(CrawlPage.crawl_job_id == job_id)
            .order_by(CrawlPage.depth, CrawlPage.created_at)
        )
        return [CrawlPageResponse.model_validate(p) for p in result.scalars()]

    # ── Worker-side processing ────────────────────────────────────────────

    async def process_crawl_job(self, job_id: uuid.UUID) -> None:
        """
        Called by the Service Bus worker to execute the full crawl.

        Orchestrates: authenticate → BFS crawl → persist pages →
        optional AI analysis → mark job COMPLETED/FAILED.
        """
        from playwright.async_api import async_playwright

        job = await self._db.get(CrawlJob, job_id)
        if not job:
            logger.error("crawl_job_not_found", job_id=str(job_id))
            return

        # Mark PROCESSING
        job.status = CrawlJobStatus.PROCESSING
        job.started_at = datetime.now(timezone.utc)
        await self._db.flush()

        try:
            async with async_playwright() as pw:
                browser = await pw.chromium.launch(headless=True)
                context = await browser.new_context(
                    viewport={"width": 1920, "height": 1080},
                    ignore_https_errors=True,
                )
                try:
                    result = await self._run_crawler(context, job)
                finally:
                    await context.close()
                    await browser.close()

            # Update job with results
            job.status = CrawlJobStatus.COMPLETED
            job.completed_at = datetime.now(timezone.utc)
            job.pages_found = len(result.pages)
            await self._db.flush()

            logger.info(
                "crawl_job_completed",
                job_id=str(job_id),
                pages=len(result.pages),
                duration_ms=result.duration_ms,
            )

            # Optional: trigger AI analysis
            if job.generate_scripts and result.pages:
                await self._trigger_ai_analysis(job, result)

        except Exception as exc:
            logger.exception("crawl_job_failed", job_id=str(job_id), error=str(exc))
            job.status = CrawlJobStatus.FAILED
            job.completed_at = datetime.now(timezone.utc)
            job.error_message = str(exc)[:1000]
            await self._db.flush()
            raise

    async def _run_crawler(self, context: Any, job: CrawlJob) -> Any:
        """Instantiate the correct crawler and run it."""
        auth_config_dict: dict[str, Any] = {}
        if job.auth_config:
            try:
                auth_config_dict = json.loads(job.auth_config)
            except Exception:
                pass

        job_config = {
            "job_id": str(job.id),
            "project_id": str(job.project_id),
            "tenant_id": str(job.tenant_id),
            "target_url": job.target_url or "",
            "launchpad_url": job.launchpad_url or "",
            "max_pages": job.max_pages,
            "auth_config": {"type": job.auth_type.value, **auth_config_dict},
            "generate_scripts": job.generate_scripts,
        }

        if job.crawler_type == CrawlerType.SAP_FIORI:
            from app.crawler.sap_fiori_crawler import SAPFioriCrawler
            crawler = SAPFioriCrawler(context, job_config)
        else:
            from app.crawler.web_crawler import WebUICrawler
            crawler = WebUICrawler(context, job_config)

        return await crawler.crawl()

    async def _trigger_ai_analysis(self, job: CrawlJob, result: Any) -> None:
        """
        For each discovered page, call the AI analysis chain to generate
        requirements and then test scripts via Service Bus.
        """
        from app.ai.chains import GenerationContext, analyze_crawl_page
        from app.ai.client import get_ai_client
        import json as _json

        ctx = GenerationContext(
            company_id=job.tenant_id,
            project_id=job.project_id,
        )
        client = get_ai_client()
        scripts_generated = 0

        for page_data in result.pages[:50]:  # Cap at 50 pages to control cost
            try:
                elements_json = _json.dumps(
                    [
                        {
                            "tag": e.tag,
                            "type": e.type,
                            "label": e.label or e.text,
                            "is_interactive": e.is_interactive,
                        }
                        for e in page_data.ui_elements[:30]
                    ]
                )
                outbound_json = _json.dumps(page_data.links[:20])

                requirements, _ = await analyze_crawl_page(
                    page_url=page_data.url,
                    page_title=page_data.title or "",
                    elements_json=elements_json,
                    outbound_links_json=outbound_json,
                    context=ctx,
                    client=client,
                )

                if requirements:
                    scripts_generated += len(requirements)
                    logger.info(
                        "crawl_ai_requirements",
                        url=page_data.url,
                        count=len(requirements),
                    )
            except Exception as exc:
                logger.warning(
                    "crawl_ai_analysis_failed", url=page_data.url, error=str(exc)
                )

        # Update scripts_generated count
        job.scripts_generated = scripts_generated
        await self._db.flush()
