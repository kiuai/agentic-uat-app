"""Abstract base class for all KAATS crawlers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from playwright.async_api import BrowserContext


@dataclass
class CrawlStep:
    step: int
    action: str  # navigate, click, fill, select, hover
    url: str | None = None
    selector: str | None = None
    value: str | None = None
    expected_state: str | None = None


@dataclass
class CrawlFlow:
    flow_id: str
    name: str
    steps: list[CrawlStep] = field(default_factory=list)
    screenshot_uris: list[str] = field(default_factory=list)


@dataclass
class CrawlMap:
    job_id: str
    project_id: str
    tenant_id: str
    crawler_type: str
    target_url: str
    pages_visited: int
    flows: list[CrawlFlow]
    metadata: dict[str, Any] = field(default_factory=dict)


class BaseCrawler(ABC):
    def __init__(self, context: BrowserContext, job_config: dict[str, Any]) -> None:
        self._context = context
        self._config = job_config

    @abstractmethod
    async def run(self) -> CrawlMap:
        """Execute the crawl and return a structured map."""
        ...

    async def _take_screenshot(self, page: Any, blob_service: Any, tenant_id: str, index: int) -> str | None:
        """Capture a screenshot and upload to Blob Storage. Returns blob URI or None on error."""
        try:
            import uuid
            screenshot_bytes = await page.screenshot(type="jpeg", quality=90)
            path = f"crawls/{self._config.get('job_id', 'unknown')}/screenshots/{index:04d}.jpg"
            from app.services.blob_service import BlobService
            bs = BlobService()
            return await bs.upload(
                uuid.UUID(tenant_id), path, screenshot_bytes, "image/jpeg"
            )
        except Exception:
            return None
