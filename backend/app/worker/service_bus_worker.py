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
import signal
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
        self._shutdown_event = asyncio.Event()

    def _register_signal_handlers(self) -> None:
        """Register SIGTERM and SIGINT handlers for graceful shutdown."""
        loop = asyncio.get_event_loop()

        def _handle_signal(sig: int) -> None:
            logger.info("worker_shutdown_signal_received", signal=sig)
            self._running = False
            self._shutdown_event.set()

        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, _handle_signal, sig)

    async def run(self) -> None:
        logger.info("worker_starting")
        configure_logging(self._settings.log_level)
        self._register_signal_handlers()

        async with async_playwright() as pw:
            self._playwright = pw
            async with ServiceBusClient.from_connection_string(
                self._settings.azure_service_bus_connection_string
            ) as client:
                tasks = await asyncio.gather(
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
                    return_exceptions=True,
                )
                logger.info("worker_stopped")

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
                if not self._running:
                    # Abandon current message so it can be reprocessed after restart
                    await receiver.abandon_message(message)
                    break
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
            from sqlalchemy import select
            from app.ai.chains import (
                GenerationContext,
                check_requirement_quality,
                classify_requirement,
                generate_test_cases_from_requirement,
                generate_script_from_test_cases,
            )
            from app.ai.client import get_ai_client
            from app.models.job import Job as JobModel
            from app.models.project import Project
            from app.models.requirement import Requirement, RequirementStatus
            from app.models.test_script import ScriptFormat, ScriptStatus, TestScript
            from app.cosmos import get_tenant_container

            # ── 1. Load job + project metadata ────────────────────────────
            factory = get_session_factory()
            async with factory() as session:
                await set_tenant_context(session, uuid.UUID(tenant_id))
                job = await session.get(JobModel, uuid.UUID(job_id))
                input_data = json.loads(job.input_payload or "{}")
                project_id_uuid = job.project_id

                project = await session.get(Project, project_id_uuid)

            project_id = str(project_id_uuid)
            requirement_ids: list[str] = input_data.get("requirement_ids", [])
            output_format_strs: list[str] = input_data.get("output_formats", ["playwright_ts"])
            gen_config: dict[str, Any] = input_data.get("generation_config", {})

            output_formats = [ScriptFormat(f) for f in output_format_strs if f in ScriptFormat._value2member_map_]
            if not output_formats:
                output_formats = [ScriptFormat.PLAYWRIGHT_TS]

            ctx = GenerationContext(
                company_id=uuid.UUID(tenant_id),
                project_id=project_id_uuid,
                base_url=project.base_url or "https://example.com" if project else "https://example.com",
                system_type=project.system_type.value if project else "WEB",
                company_name=project.name if project else "KAATS",
                industry=(project.settings or {}).get("industry", "Software") if project else "Software",
                feature_name=project.name if project else "Application",
                include_assertions=gen_config.get("include_assertions", True),
                include_negative_cases=gen_config.get("include_negative_cases", False),
                max_steps_per_script=gen_config.get("max_steps_per_script", 20),
            )

            # ── 2. Load requirements from SQL ─────────────────────────────
            requirements = await self._load_requirements(tenant_id, requirement_ids)
            if not requirements:
                logger.warning("ai_job_no_requirements", job_id=job_id)
                await self._update_job_status(
                    job_id, tenant_id, JobStatus.FAILED,
                    error_message="No requirements found for the given IDs.",
                )
                return

            ai_client = get_ai_client()
            script_cosmos_ids: list[str] = []
            total_tokens = 0

            # ── 3. Per-requirement pipeline ───────────────────────────────
            for req in requirements:
                req_title = req["title"]
                req_content = req["content"] or req_title
                req_id = req["id"]
                business_domain = req.get("business_domain") or "GENERAL"
                priority = req.get("priority") or "MEDIUM"

                # Quality gate (warn only — don't block generation)
                try:
                    quality, q_usage = await check_requirement_quality(
                        req_title, req_content, context=ctx, client=ai_client
                    )
                    total_tokens += q_usage.total_tokens
                    logger.info(
                        "requirement_quality",
                        job_id=job_id,
                        req_id=req_id,
                        score=quality.quality_score,
                        verdict=quality.testability_verdict,
                    )
                    if quality.testability_verdict == "UNTESTABLE":
                        logger.warning(
                            "requirement_untestable",
                            job_id=job_id,
                            req_id=req_id,
                            suggestions=quality.improvement_suggestions,
                        )
                        continue
                except Exception as qe:
                    logger.warning("quality_check_failed", req_id=req_id, error=str(qe))

                # Stage 1: requirement → structured test cases
                test_cases, tc_usage = await generate_test_cases_from_requirement(
                    req_title,
                    req_content,
                    context=ctx,
                    business_domain=business_domain,
                    priority=priority,
                    client=ai_client,
                )
                total_tokens += tc_usage.total_tokens

                if not test_cases:
                    logger.warning("no_test_cases_generated", req_id=req_id)
                    continue

                # Stage 2: test cases → scripts for every requested format
                scripts_by_format: dict[str, str] = {}
                for fmt in output_formats:
                    try:
                        script = await generate_script_from_test_cases(
                            test_cases, fmt, context=ctx, client=ai_client
                        )
                        scripts_by_format[fmt.value] = script.content
                        total_tokens += script.usage.total_tokens
                    except ValueError as ve:
                        logger.warning(
                            "script_generation_failed",
                            req_id=req_id,
                            format=fmt.value,
                            error=str(ve),
                        )

                if not scripts_by_format:
                    continue

                # Store script content in Cosmos DB
                cosmos_doc_id = await self._store_test_script_in_cosmos(
                    tenant_id=tenant_id,
                    project_id=project_id,
                    job_id=job_id,
                    req_id=req_id,
                    req_title=req_title,
                    test_cases=[
                        {
                            "test_case_id": tc.test_case_id,
                            "title": tc.title,
                            "test_type": tc.test_type,
                            "priority": tc.priority,
                            "preconditions": tc.preconditions,
                            "steps": [
                                {
                                    "step_number": s.step_number,
                                    "action": s.action,
                                    "expected_result": s.expected_result,
                                    "input_data": s.input_data,
                                }
                                for s in tc.test_steps
                            ],
                            "expected_outcome": tc.expected_outcome,
                        }
                        for tc in test_cases
                    ],
                    scripts=scripts_by_format,
                )
                script_cosmos_ids.append(cosmos_doc_id)

                # Create SQL TestScript metadata row
                await self._create_test_script_row(
                    tenant_id=tenant_id,
                    project_id=project_id_uuid,
                    requirement_id=uuid.UUID(req_id),
                    job_id=uuid.UUID(job_id),
                    title=f"AI Generated: {req_title}",
                    cosmos_doc_id=cosmos_doc_id,
                    output_formats=output_formats,
                )

                # Mark requirement as processed
                await self._mark_requirement_processed(tenant_id, req_id, RequirementStatus.PROCESSED)

            # ── 4. Update job ─────────────────────────────────────────────
            # Store index of all script cosmos IDs as the job result
            container = get_tenant_container(uuid.UUID(tenant_id))
            index_doc: dict[str, Any] = {
                "id": f"gen-result-{job_id}",
                "schema_version": 1,
                "type": "generation_result",
                "project_id": project_id,
                "tenant_id": tenant_id,
                "job_id": job_id,
                "requirement_ids": requirement_ids,
                "script_cosmos_ids": script_cosmos_ids,
                "total_tokens": total_tokens,
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
            await container.upsert_item(index_doc)

            await self._update_job_status(
                job_id, tenant_id, JobStatus.COMPLETED, cosmos_result_id=index_doc["id"]
            )
            logger.info(
                "ai_job_completed",
                job_id=job_id,
                scripts_count=len(script_cosmos_ids),
                total_tokens=total_tokens,
            )

        except Exception as exc:
            logger.exception("ai_job_failed", job_id=job_id, error=str(exc))
            await self._update_job_status(
                job_id, tenant_id, JobStatus.FAILED, error_message=str(exc)
            )
            raise

    async def _load_requirements(
        self, tenant_id: str, requirement_ids: list[str]
    ) -> list[dict[str, Any]]:
        """Load full requirement rows from SQL; return dicts with title/content/domain/priority."""
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
            return [
                {
                    "id": str(r.id),
                    "title": r.title,
                    "content": r.content_text or r.description or r.title,
                    "business_domain": getattr(r, "business_domain", None),
                    "priority": r.priority.value if r.priority else "MEDIUM",
                }
                for r in result.scalars()
            ]

    async def _store_test_script_in_cosmos(
        self,
        tenant_id: str,
        project_id: str,
        job_id: str,
        req_id: str,
        req_title: str,
        test_cases: list[dict[str, Any]],
        scripts: dict[str, str],
    ) -> str:
        """Write a test_script document to Cosmos DB; return its ID."""
        from app.cosmos import get_tenant_container

        container = get_tenant_container(uuid.UUID(tenant_id))
        now = datetime.now(timezone.utc).isoformat()
        doc_id = f"ts-gen-{job_id}-{req_id[:8]}"

        doc: dict[str, Any] = {
            "id": doc_id,
            "schema_version": 1,
            "type": "test_script",
            "project_id": project_id,
            "tenant_id": tenant_id,
            "source_job_id": job_id,
            "requirement_id": req_id,
            "title": f"AI Generated: {req_title}",
            "status": "DRAFT",
            "version": 1,
            "test_cases": test_cases,
            "scripts": scripts,
            "created_at": now,
            "updated_at": now,
        }
        await container.upsert_item(doc)
        return doc_id

    async def _create_test_script_row(
        self,
        tenant_id: str,
        project_id: uuid.UUID,
        requirement_id: uuid.UUID,
        job_id: uuid.UUID,
        title: str,
        cosmos_doc_id: str,
        output_formats: list[Any],
    ) -> None:
        """Create a TestScript SQL metadata row for the generated script."""
        from app.models.test_script import TestScript, ScriptStatus, ScriptFormat

        factory = get_session_factory()
        async with factory() as session:
            await set_tenant_context(session, uuid.UUID(tenant_id))
            # Use primary output format as the format column value
            primary_fmt = output_formats[0] if output_formats else ScriptFormat.PLAYWRIGHT_TS
            script = TestScript(
                id=uuid.uuid4(),
                tenant_id=uuid.UUID(tenant_id),
                project_id=project_id,
                requirement_id=requirement_id,
                title=title,
                format=primary_fmt,
                status=ScriptStatus.DRAFT,
                cosmos_doc_id=cosmos_doc_id,
                current_version=1,
                is_ai_generated=True,
                created_by=job_id,  # use job_id as proxy for system-generated
            )
            session.add(script)
            await session.commit()

    async def _mark_requirement_processed(
        self, tenant_id: str, req_id: str, new_status: Any
    ) -> None:
        from app.models.requirement import Requirement

        factory = get_session_factory()
        async with factory() as session:
            await set_tenant_context(session, uuid.UUID(tenant_id))
            req = await session.get(Requirement, uuid.UUID(req_id))
            if req:
                req.status = new_status
                await session.commit()

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

            # Optionally run AI analysis on discovered flows to generate test scripts
            if payload.get("generate_scripts", False) and crawl_map.flows:
                await self._generate_scripts_from_crawl(
                    job_id=job_id,
                    tenant_id=tenant_id,
                    project_id=str(crawl_map.project_id),
                    crawl_map=crawl_map,
                )

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


    async def _generate_scripts_from_crawl(
        self,
        job_id: str,
        tenant_id: str,
        project_id: str,
        crawl_map: Any,
    ) -> None:
        """Run AI flow-analysis on each discovered flow and store resulting test scripts."""
        from app.ai.chains import GenerationContext, analyze_crawl_flow, generate_script_from_test_cases
        from app.ai.client import get_ai_client
        from app.models.test_script import ScriptFormat

        ai_client = get_ai_client()
        ctx = GenerationContext(
            company_id=uuid.UUID(tenant_id),
            project_id=uuid.UUID(project_id),
            base_url=crawl_map.target_url or "https://example.com",
            feature_name=crawl_map.crawler_type,
        )

        for flow in crawl_map.flows:
            try:
                flow_pages = [{"url": s.url, "action": s.action} for s in flow.steps]
                elements_summary = "; ".join(
                    f"step {s.step}: {s.action} on {s.selector or s.url}"
                    for s in flow.steps[:10]
                )

                test_cases, _ = await analyze_crawl_flow(
                    flow_name=flow.name,
                    flow_pages=flow_pages,
                    elements_summary=elements_summary,
                    context=ctx,
                    client=ai_client,
                )

                if not test_cases:
                    continue

                # Generate Playwright TS by default for crawl-derived scripts
                script = await generate_script_from_test_cases(
                    test_cases,
                    ScriptFormat.PLAYWRIGHT_TS,
                    context=ctx,
                    client=ai_client,
                )

                await self._store_test_script_in_cosmos(
                    tenant_id=tenant_id,
                    project_id=project_id,
                    job_id=job_id,
                    req_id=flow.flow_id,
                    req_title=flow.name,
                    test_cases=[
                        {
                            "test_case_id": tc.test_case_id,
                            "title": tc.title,
                            "test_type": tc.test_type,
                            "priority": tc.priority,
                            "preconditions": tc.preconditions,
                            "steps": [
                                {
                                    "step_number": s.step_number,
                                    "action": s.action,
                                    "expected_result": s.expected_result,
                                    "input_data": s.input_data,
                                }
                                for s in tc.test_steps
                            ],
                            "expected_outcome": tc.expected_outcome,
                        }
                        for tc in test_cases
                    ],
                    scripts={ScriptFormat.PLAYWRIGHT_TS.value: script.content},
                )
                logger.info(
                    "crawl_flow_scripts_generated",
                    job_id=job_id,
                    flow_id=flow.flow_id,
                    test_case_count=len(test_cases),
                )
            except Exception as exc:
                logger.warning(
                    "crawl_flow_script_failed",
                    job_id=job_id,
                    flow_id=flow.flow_id,
                    error=str(exc),
                )


if __name__ == "__main__":
    asyncio.run(JobWorker().run())
