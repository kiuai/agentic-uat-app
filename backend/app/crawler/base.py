"""Abstract base class and shared data structures for all KAATS crawlers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from playwright.async_api import BrowserContext, Page


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


@dataclass
class AuthConfig:
    """Authentication configuration for crawling protected applications."""

    type: str = "none"  # none | form | basic | bearer | cookie | saml
    # Resolved at runtime from Key Vault — never stored as plain text
    username: str = ""
    password: str = ""
    bearer_token: str = ""
    cookies: list[dict[str, Any]] = field(default_factory=list)
    # Form auth selectors (override defaults)
    username_selector: str = "[name=username],[name=email],[id=email],[id=username]"
    password_selector: str = "[type=password],[name=password]"
    submit_selector: str = "button[type=submit],[type=submit]"
    login_url: str = ""
    # Post-login validation: wait for this selector to confirm success
    post_login_selector: str = ""
    post_login_url_pattern: str = ""


@dataclass
class CrawlerConfig:
    """Runtime configuration for a crawl job."""

    max_depth: int = 5
    max_pages: int = 100
    include_patterns: list[str] = field(default_factory=list)
    exclude_patterns: list[str] = field(default_factory=list)
    same_origin_only: bool = True
    auth_config: AuthConfig = field(default_factory=AuthConfig)
    wait_for_selector: str = "body"
    interaction_timeout: int = 30_000  # ms
    page_load_timeout: int = 30_000   # ms
    interaction_delay_ms: int = 500
    generate_scripts: bool = True
    # SAP-specific
    tile_groups: list[str] = field(default_factory=list)
    # Debug
    debug_screenshots: bool = False


# ---------------------------------------------------------------------------
# Page-level data structures
# ---------------------------------------------------------------------------


class PageType(str, Enum):
    FORM = "FORM"
    LIST = "LIST"
    DETAIL = "DETAIL"
    DASHBOARD = "DASHBOARD"
    NAVIGATION = "NAVIGATION"
    LOGIN = "LOGIN"
    UNKNOWN = "UNKNOWN"


@dataclass
class UIElement:
    """A single interactive element discovered on a page."""

    tag: str
    type: str | None = None
    id: str | None = None
    name: str | None = None
    placeholder: str | None = None
    label: str | None = None
    href: str | None = None
    text: str | None = None
    role: str | None = None
    aria_label: str | None = None
    is_interactive: bool = True
    selector: str | None = None
    # SAP-specific
    sap_control_type: str | None = None


@dataclass
class FormData:
    """Structure of a discovered HTML form."""

    form_id: str | None = None
    action_url: str | None = None
    method: str = "POST"
    fields: list[UIElement] = field(default_factory=list)
    submit_selector: str | None = None
    submit_text: str | None = None


@dataclass
class PageData:
    """Structured information extracted from a single crawled page."""

    url: str
    title: str = ""
    page_type: PageType = PageType.UNKNOWN
    ui_elements: list[UIElement] = field(default_factory=list)
    forms: list[FormData] = field(default_factory=list)
    links: list[str] = field(default_factory=list)
    navigation_items: list[str] = field(default_factory=list)
    screenshot_blob_url: str | None = None
    page_load_time_ms: int = 0
    depth: int = 0
    page_hash: str | None = None
    # SAP-specific extension
    sap_metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class FlowEdge:
    """Directed edge in the page flow graph."""

    from_url: str
    to_url: str
    trigger_element: str | None = None   # CSS selector of the element clicked
    trigger_action: str = "navigate"      # navigate | click | submit | redirect


@dataclass
class CrawlResult:
    """Complete output of a crawl run."""

    pages: list[PageData] = field(default_factory=list)
    flow_graph: list[FlowEdge] = field(default_factory=list)
    duration_ms: int = 0
    crawler_type: str = "WEB"
    target_url: str = ""
    job_id: str = ""
    project_id: str = ""
    tenant_id: str = ""
    error_count: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Backward-compat structures (used by worker service_bus_worker.py)
# ---------------------------------------------------------------------------


@dataclass
class CrawlStep:
    step: int
    action: str
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
    """Backward-compat return type for the worker's _handle_crawl_job."""

    job_id: str
    project_id: str
    tenant_id: str
    crawler_type: str
    target_url: str
    pages_visited: int
    flows: list[CrawlFlow]
    metadata: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Abstract base
# ---------------------------------------------------------------------------


class BaseCrawler(ABC):
    """
    Abstract base for all KAATS crawlers.

    Subclasses implement crawl() (rich typed result) and expose run() which
    converts the result to the backward-compatible CrawlMap for the worker.
    """

    def __init__(self, context: BrowserContext, job_config: dict[str, Any]) -> None:
        self._context = context
        self._config = job_config
        self._crawler_config = self._build_config(job_config)

    def _build_config(self, job_config: dict[str, Any]) -> CrawlerConfig:
        raw_auth = job_config.get("auth_config") or {}
        auth = AuthConfig(
            type=raw_auth.get("type", "none"),
            username=raw_auth.get("username", ""),
            password=raw_auth.get("password", ""),
            bearer_token=raw_auth.get("bearer_token", ""),
            cookies=raw_auth.get("cookies", []),
            username_selector=raw_auth.get(
                "username_selector",
                "[name=username],[name=email],[id=email],[id=username]",
            ),
            password_selector=raw_auth.get("password_selector", "[type=password],[name=password]"),
            submit_selector=raw_auth.get("submit_selector", "button[type=submit],[type=submit]"),
            login_url=raw_auth.get("login_url", ""),
            post_login_selector=raw_auth.get("post_login_selector", ""),
            post_login_url_pattern=raw_auth.get("post_login_url_pattern", ""),
        )
        return CrawlerConfig(
            max_depth=job_config.get("max_depth", 5),
            max_pages=job_config.get("max_pages", 100),
            include_patterns=job_config.get("include_patterns", []),
            exclude_patterns=job_config.get("exclude_patterns", []),
            same_origin_only=job_config.get("same_origin_only", True),
            auth_config=auth,
            wait_for_selector=job_config.get("wait_for_selector", "body"),
            interaction_timeout=job_config.get("interaction_timeout", 30_000),
            page_load_timeout=job_config.get("page_load_timeout_ms", 30_000),
            interaction_delay_ms=job_config.get("interaction_delay_ms", 500),
            generate_scripts=job_config.get("generate_scripts", True),
            tile_groups=job_config.get("tile_groups", []),
            debug_screenshots=job_config.get("debug_screenshots", False),
        )

    @abstractmethod
    async def crawl(self) -> CrawlResult:
        """Execute the full crawl and return a typed CrawlResult."""
        ...

    @abstractmethod
    async def analyze_page(self, page: Page, url: str) -> PageData:
        """Extract structured information from a loaded page."""
        ...

    async def run(self) -> CrawlMap:
        """
        Backward-compatible wrapper: calls crawl() and converts to CrawlMap.
        Used by service_bus_worker._handle_crawl_job().
        """
        result = await self.crawl()
        flows = [
            CrawlFlow(
                flow_id=f"flow-{i:04d}",
                name=p.title or p.url,
                steps=[
                    CrawlStep(
                        step=1,
                        action="navigate",
                        url=p.url,
                        expected_state=f"Page '{p.title}' loaded",
                    )
                ],
                screenshot_uris=[p.screenshot_blob_url] if p.screenshot_blob_url else [],
            )
            for i, p in enumerate(result.pages, 1)
        ]
        return CrawlMap(
            job_id=result.job_id,
            project_id=result.project_id,
            tenant_id=result.tenant_id,
            crawler_type=result.crawler_type,
            target_url=result.target_url,
            pages_visited=len(result.pages),
            flows=flows,
            metadata=result.metadata,
        )

    async def _take_screenshot(self, page: Page, tenant_id: str, index: int) -> str | None:
        """Capture a screenshot and upload to Blob Storage. Returns blob URI or None."""
        try:
            import uuid as _uuid
            screenshot_bytes = await page.screenshot(type="jpeg", quality=85)
            path = (
                f"crawls/{self._config.get('job_id', 'unknown')}"
                f"/screenshots/{index:04d}.jpg"
            )
            from app.services.blob_service import BlobService
            return await BlobService().upload(
                _uuid.UUID(tenant_id), path, screenshot_bytes, "image/jpeg"
            )
        except Exception:
            return None

    async def _save_crawl_page(
        self, page_data: PageData, crawl_job_id: str, tenant_id: str
    ) -> None:
        """Persist a CrawlPage record to Azure SQL (fire-and-forget, errors logged)."""
        import hashlib
        import json
        import uuid as _uuid

        try:
            from app.database import get_session_factory, set_tenant_context
            from app.models.crawl_job import CrawlPage

            elements_json = json.dumps(
                [
                    {
                        "tag": e.tag,
                        "type": e.type,
                        "label": e.label or e.text,
                        "selector": e.selector,
                        "is_interactive": e.is_interactive,
                    }
                    for e in page_data.ui_elements[:100]
                ]
            )
            page_hash = hashlib.sha256(elements_json.encode()).hexdigest()

            factory = get_session_factory()
            async with factory() as session:
                await set_tenant_context(session, _uuid.UUID(tenant_id))
                row = CrawlPage(
                    id=_uuid.uuid4(),
                    tenant_id=_uuid.UUID(tenant_id),
                    crawl_job_id=_uuid.UUID(crawl_job_id),
                    url=page_data.url[:2000],
                    title=page_data.title[:500] if page_data.title else None,
                    page_hash=page_hash,
                    depth=page_data.depth,
                    elements_json=elements_json,
                    screenshot_uri=page_data.screenshot_blob_url,
                )
                session.add(row)
                await session.commit()
        except Exception as exc:
            import structlog as _sl
            _sl.get_logger(__name__).warning(
                "crawl_page_save_failed", url=page_data.url, error=str(exc)
            )
