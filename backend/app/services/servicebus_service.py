"""Azure Service Bus publisher for job dispatch."""

from __future__ import annotations

import json
from typing import Any

import structlog
from azure.servicebus.aio import ServiceBusClient
from azure.servicebus import ServiceBusMessage

from app.config import get_settings

logger = structlog.get_logger(__name__)


class ServiceBusService:
    def __init__(self) -> None:
        self._settings = get_settings()

    async def _publish(self, topic: str, body: dict[str, Any]) -> None:
        connection_string = self._settings.azure_service_bus_connection_string
        async with ServiceBusClient.from_connection_string(connection_string) as client:
            async with client.get_topic_sender(topic_name=topic) as sender:
                message = ServiceBusMessage(
                    body=json.dumps(body),
                    content_type="application/json",
                )
                await sender.send_messages(message)
                logger.info("servicebus_message_sent", topic=topic, job_id=body.get("job_id"))

    async def publish_ai_job(
        self, job_id: str, tenant_id: str, payload: dict[str, Any]
    ) -> None:
        await self._publish(
            self._settings.azure_service_bus_ai_jobs_topic,
            {"job_id": job_id, "tenant_id": tenant_id, "payload": payload},
        )

    async def publish_crawl_job(
        self, job_id: str, tenant_id: str, payload: dict[str, Any]
    ) -> None:
        await self._publish(
            self._settings.azure_service_bus_crawl_jobs_topic,
            {"job_id": job_id, "tenant_id": tenant_id, "payload": payload},
        )
