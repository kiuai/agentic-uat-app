"""
Azure Service Bus worker — processes AI generation and crawler jobs.

Run standalone: python -m app.worker.service_bus_worker

Subscribes to:
- ai-jobs topic      → runs AI test generation pipeline
- crawl-jobs topic   → runs Playwright crawler

After processing, updates job status in Azure SQL and stores results in Cosmos DB.
"""

from __future__ import annotations

import asyncio
import json
import uuid
from datetime import datetime, timezone
from typing import Any

import structlog
from azure.servicebus.aio import ServiceBusClient
from azure.servicebus import ServiceBusReceivedMessage
from playwright.async_api import async_playwright

from app.config import get_settings
from app.cosmos import get_tenant_container
from app.database import get_session_factory, set_tenant_context
from app.logging_config import configure_logging
from app.models.job import Job, JobStatus, JobType

logger = structlog.get_logger(__name__)


class JobWorker:
    def __init__(self) -> None:
        self._settings = get_settings()
        self._running = True

    async def run(self) -> None:
        logger.info("worker_starting")
        configure_logging(self._settings.log_level)

        async with async_playwright() as pw:
            self._playwright = pw
            async with ServiceBusClient.from_connection_string(
                self._settings.azure_service_bus_connection_string
            ) as client:
                await asyncio.gather(
                    self._consume_topic(
                        client,
                        self._settings.azure_service_bus_ai_jobs_topic,
                        self._handle_ai_job,
                    ),
                    self._consume_topic(
                        client,
                        self._settings.azure_service_bus_crawl_jobs_topic,
                        self._handle_crawl_job,
                    ),
                )

    async def _consume_topic(
        self,
        client: ServiceBusClient,
        topic: str,
        handler: Any,
    ) -> None:
        subscription = self._settings.azure_service_bus_subscription_name
        async with client.get_subscription_receiver(
            topic_name=topic,
            subscription_name=subscription,
            max_wait_time=5,
        ) as receiver:
            logger.info("worker_listening", topic=topic)
            async for message in receiver:
                try:
                    body = json.loads(str(message))
                    await handler(body)
                    await receiver.complete_message(message)
                    logger.info("message_processed", topic=topic, job_id=body.get("job_id"))
                except Exception as exc:
                    logger.exception(
                        "message_processing_failed",
                        topic=topic,
                        error=str(exc),
                    )
                    await receiver.dead_letter_message(
                        message, reason="ProcessingError", error_description=str(exc)
                    )

    async def _update_job_status(
        self,
        job_id: str,
        tenant_id: str,
        status: JobStatus,
        cosmos_result_id: str | None = None,
        error_message: str | None = None,
    ) -> None:
        factory = get_session_factory()
        async with factory() as session:
            await set_tenant_context(session, uuid.UUID(tenant_id))
            job = await session.get(Job, uuid.UUID(job_id))
            if job:
                job.status = status
                job.completed_at = datetime.now(timezone.utc)
                if cosmos_result_id:
                    job.cosmos_result_id = cosmos_result_id
                if error_message:
                    job.error_message = error_message
                if status == JobStatus.PROCESSING:
                    job.started_at = datetime.now(timezone.utc)
                    job.completed_at = None
                await session.commit()

    async def _handle_ai_job(self, message: dict[str, Any]) -> None:
        job_id = message["job_id"]
        tenant_id = message["tenant_id"]
        payload = message["payload"]

        await self._update_job_status(job_id, tenant_id, JobStatus.PROCESSING)
        logger.info("ai_job_processing", job_id=job_id)

        try:
            from app.ai.chains import run_decompose, run_generate_steps, run_format_playwright_ts
            from app.models.job import Job as JobModel

            factory = get_session_factory()
            async with factory() as session:
                await set_tenant_context(session, uuid.UUID(tenant_id))
                job = await session.get(JobModel, uuid.UUID(job_id))
                input_data = json.loads(job.input_payload or "{}")
                project_id = str(job.project_id)

            requirement_ids = input_data.get("requirement_ids", [])
            output_formats = input_data.get("output_formats", ["playwright_ts"])
            gen_config = input_data.get("generation_config", {})

            # Fetch requirement content
            req_contents = await self._fetch_requirements(tenant_id, requirement_ids)
            combined_content = "\n\n".join(req_contents)

            # Stage 1: Decompose
            scenarios = await run_decompose(combined_content)

            # Stage 2 + 3: Generate steps and format for each scenario
            all_scripts: list[dict[str, Any]] = []
            for scenario in scenarios[: gen_config.get("max_steps_per_script", 20)]:
                test_case = await run_generate_steps(scenario)
                scripts: dict[str, str] = {}

                if "playwright_ts" in output_formats:
                    scripts["playwright_ts"] = await run_format_playwright_ts(test_case)

                # Use template exporters for other formats
                from app.exporters.gherkin_exporter import GherkinExporter
                from app.exporters.pytest_exporter import PytestExporter
                from app.exporters.robot_framework_exporter import RobotFrameworkExporter
                from app.exporters.selenium_exporter import SeleniumExporter
                from app.exporters.playwright_exporter import PlaywrightExporter

                format_map = {
                    "playwright_js": PlaywrightExporter("js").export,
                    "selenium_python": SeleniumExporter().export,
                    "pytest": PytestExporter().export,
                    "robot_framework": RobotFrameworkExporter().export,
                    "gherkin": GherkinExporter().export,
                }
                for fmt in output_formats:
                    if fmt in format_map:
                        scripts[fmt] = format_map[fmt](test_case)

                all_scripts.append({
                    "scenario": scenario,
                    "test_case": test_case,
                    "scripts": scripts,
                })

            # Store result in Cosmos DB
            cosmos_doc = await self._store_scripts_in_cosmos(
                tenant_id, project_id, job_id, requirement_ids, all_scripts
            )

            await self._update_job_status(
                job_id, tenant_id, JobStatus.COMPLETED, cosmos_result_id=cosmos_doc["id"]
            )
            logger.info("ai_job_completed", job_id=job_id, scripts_count=len(all_scripts))

        except Exception as exc:
            logger.exception("ai_job_failed", job_id=job_id, error=str(exc))
            await self._update_job_status(
                job_id, tenant_id, JobStatus.FAILED, error_message=str(exc)
            )
            raise

    async def _fetch_requirements(
        self, tenant_id: str, requirement_ids: list[str]
    ) -> list[str]:
        from sqlalchemy import select
        from app.models.requirement import Requirement

        factory = get_session_factory()
        async with factory() as session:
            await set_tenant_context(session, uuid.UUID(tenant_id))
            result = await session.execute(
                select(Requirement).where(
                    Requirement.id.in_([uuid.UUID(r) for r in requirement_ids])
                )
            )
            return [r.content_text or r.title for r in result.scalars()]

    async def _store_scripts_in_cosmos(
        self,
        tenant_id: str,
        project_id: str,
        job_id: str,
        requirement_ids: list[str],
        all_scripts: list[dict[str, Any]],
    ) -> dict[str, Any]:
        container = get_tenant_container(uuid.UUID(tenant_id))
        now = datetime.now(timezone.utc).isoformat()

        doc: dict[str, Any] = {
            "id": f"gen-result-{job_id}",
            "schema_version": 1,
            "type": "generation_result",
            "project_id": project_id,
            "tenant_id": tenant_id,
            "job_id": job_id,
            "requirement_ids": requirement_ids,
            "scripts": all_scripts,
            "created_at": now,
        }
        await container.upsert_item(doc)
        return doc

    async def _handle_crawl_job(self, message: dict[str, Any]) -> None:
        job_id = message["job_id"]
        tenant_id = message["tenant_id"]
        payload = message["payload"]

        await self._update_job_status(job_id, tenant_id, JobStatus.PROCESSING)
        logger.info("crawl_job_processing", job_id=job_id)

        try:
            crawler_type = payload.get("crawler_type", "WEB")
            browser = await self._playwright.chromium.launch(headless=True)
            context = await browser.new_context(
                viewport={"width": 1920, "height": 1080},
                ignore_https_errors=True,
            )

            job_config = {**payload, "job_id": job_id, "tenant_id": tenant_id}

            try:
                if crawler_type == "SAP_FIORI":
                    from app.crawler.sap_fiori_crawler import SAPFioriCrawler
                    crawler = SAPFioriCrawler(context, job_config)
                else:
                    from app.crawler.web_crawler import WebCrawler
                    crawler = WebCrawler(context, job_config)

                crawl_map = await crawler.run()
            finally:
                await context.close()
                await browser.close()

            # Store crawl map in Cosmos DB
            cosmos_doc = await self._store_crawl_map(tenant_id, crawl_map)

            await self._update_job_status(
                job_id, tenant_id, JobStatus.COMPLETED, cosmos_result_id=cosmos_doc["id"]
            )
            logger.info(
                "crawl_job_completed",
                job_id=job_id,
                pages=crawl_map.pages_visited,
            )

        except Exception as exc:
            logger.exception("crawl_job_failed", job_id=job_id, error=str(exc))
            await self._update_job_status(
                job_id, tenant_id, JobStatus.FAILED, error_message=str(exc)
            )
            raise

    async def _store_crawl_map(
        self, tenant_id: str, crawl_map: Any
    ) -> dict[str, Any]:
        from dataclasses import asdict
        container = get_tenant_container(uuid.UUID(tenant_id))
        now = datetime.now(timezone.utc).isoformat()

        doc: dict[str, Any] = {
            "id": f"crawl-{crawl_map.job_id}",
            "schema_version": 1,
            "type": "crawl_map",
            "job_id": crawl_map.job_id,
            "project_id": crawl_map.project_id,
            "tenant_id": crawl_map.tenant_id,
            "crawler_type": crawl_map.crawler_type,
            "target_url": crawl_map.target_url,
            "pages_visited": crawl_map.pages_visited,
            "flows": [
                {
                    "flow_id": f.flow_id,
                    "name": f.name,
                    "steps": [
                        {
                            "step": s.step,
                            "action": s.action,
                            "url": s.url,
                            "selector": s.selector,
                            "value": s.value,
                            "expected_state": s.expected_state,
                        }
                        for s in f.steps
                    ],
                    "screenshot_uris": f.screenshot_uris,
                }
                for f in crawl_map.flows
            ],
            "metadata": crawl_map.metadata,
            "created_at": now,
        }
        await container.upsert_item(doc)
        return doc


if __name__ == "__main__":
    asyncio.run(JobWorker().run())
