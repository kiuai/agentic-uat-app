"""
Generic web UI crawler — BFS page traversal with structured element extraction.

Algorithm
---------
1. Authenticate (form / basic / bearer / cookie)
2. BFS from seed URL; respect max_depth and max_pages
3. For each page: analyze_page() → screenshot → persist CrawlPage row
4. Build flow graph (FlowEdge per navigation)
5. Return CrawlResult

Page-type classification heuristics drive AI prompt selection downstream.
"""

from __future__ import annotations

import asyncio
import hashlib
import re
import time
from collections import deque
from typing import Any
from urllib.parse import urljoin, urlparse

import structlog
from playwright.async_api import BrowserContext, Page

from app.crawler.base import (
    AuthConfig,
    BaseCrawler,
    CrawlResult,
    FlowEdge,
    FormData,
    PageData,
    PageType,
    UIElement,
)

logger = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# JS snippets evaluated inside the page
# ---------------------------------------------------------------------------

_JS_EXTRACT_ELEMENTS = """() => {
    const INTERACTIVE_SELECTORS = [
        'a[href]', 'button', 'input', 'select', 'textarea',
        '[role="button"]', '[role="link"]', '[role="menuitem"]',
        '[role="tab"]', '[role="checkbox"]', '[role="radio"]',
        '[contenteditable="true"]',
    ].join(',');

    function getLabel(el) {
        // 1. aria-label / aria-labelledby
        if (el.ariaLabel) return el.ariaLabel;
        const labelledBy = el.getAttribute('aria-labelledby');
        if (labelledBy) {
            const lbl = document.getElementById(labelledBy);
            if (lbl) return lbl.textContent?.trim();
        }
        // 2. <label for="...">
        if (el.id) {
            const lbl = document.querySelector('label[for="' + el.id + '"]');
            if (lbl) return lbl.textContent?.trim();
        }
        // 3. Wrapping <label>
        const parent = el.closest('label');
        if (parent) return parent.textContent?.trim();
        // 4. Placeholder / visible text
        return el.placeholder || el.textContent?.trim().slice(0, 80) || null;
    }

    function buildSelector(el) {
        if (el.id) return '#' + CSS.escape(el.id);
        if (el.name) return el.tagName.toLowerCase() + '[name="' + el.name + '"]';
        const text = el.textContent?.trim().slice(0, 30);
        if (text) return el.tagName.toLowerCase() + ':has-text("' + text.replace(/"/g, '\\"') + '")';
        return el.tagName.toLowerCase();
    }

    const elements = document.querySelectorAll(INTERACTIVE_SELECTORS);
    return Array.from(elements).slice(0, 80).map(el => ({
        tag: el.tagName.toLowerCase(),
        type: el.type || el.getAttribute('type') || null,
        id: el.id || null,
        name: el.name || null,
        placeholder: el.placeholder || null,
        label: getLabel(el),
        href: el.href || null,
        text: el.textContent?.trim().slice(0, 120) || null,
        role: el.role || el.getAttribute('role') || null,
        aria_label: el.ariaLabel || el.getAttribute('aria-label') || null,
        selector: buildSelector(el),
        is_interactive: !el.disabled,
    }));
}"""

_JS_EXTRACT_FORMS = """() => {
    return Array.from(document.querySelectorAll('form')).slice(0, 10).map((form, idx) => {
        const fields = Array.from(form.querySelectorAll(
            'input:not([type=hidden]):not([type=submit]):not([type=button]),' +
            'select, textarea'
        )).slice(0, 30).map(el => {
            const lblEl = el.id
                ? document.querySelector('label[for="' + el.id + '"]')
                : el.closest('label');
            return {
                tag: el.tagName.toLowerCase(),
                type: el.type || null,
                id: el.id || null,
                name: el.name || null,
                placeholder: el.placeholder || null,
                label: lblEl ? lblEl.textContent.trim() : (el.ariaLabel || null),
                required: el.required,
            };
        });
        const submit = form.querySelector('[type=submit],button:not([type])');
        return {
            form_id: form.id || ('form-' + idx),
            action_url: form.action || null,
            method: form.method?.toUpperCase() || 'POST',
            fields,
            submit_selector: submit ? (submit.id ? '#' + submit.id : submit.tagName.toLowerCase()) : null,
            submit_text: submit ? submit.textContent?.trim() : null,
        };
    });
}"""

_JS_EXTRACT_NAV = """() => {
    const nav = document.querySelectorAll('nav a, [role=navigation] a, .nav a, .navbar a, .menu a');
    return Array.from(nav).slice(0, 30).map(a => a.textContent?.trim()).filter(Boolean);
}"""

_JS_CLASSIFY_PAGE = """() => {
    const inputs = document.querySelectorAll('input:not([type=hidden]),select,textarea').length;
    const tables = document.querySelectorAll('table,ul[role=listbox],[role=grid],[role=list]').length;
    const charts = document.querySelectorAll('canvas,[class*=chart],[class*=graph],[class*=widget]').length;
    const headings = document.querySelectorAll('h1,h2').length;
    const loginForms = document.querySelectorAll('[name=login],[id*=login],[class*=login],input[type=password]').length;

    return { inputs, tables, charts, headings, loginForms };
}"""


def _classify_page_type(signals: dict[str, int]) -> PageType:
    if signals.get("loginForms", 0) > 0:
        return PageType.LOGIN
    if signals.get("charts", 0) >= 2:
        return PageType.DASHBOARD
    if signals.get("inputs", 0) >= 3 and signals.get("tables", 0) == 0:
        return PageType.FORM
    if signals.get("tables", 0) >= 1:
        return PageType.LIST
    if signals.get("headings", 0) >= 2 and signals.get("inputs", 0) <= 1:
        return PageType.DETAIL
    return PageType.UNKNOWN


class WebUICrawler(BaseCrawler):
    """BFS web UI crawler with structured page analysis."""

    def __init__(self, context: BrowserContext, job_config: dict[str, Any]) -> None:
        super().__init__(context, job_config)
        self._visited: set[str] = set()
        self._queue: deque[tuple[str, int, str | None]] = deque()  # (url, depth, referrer)
        self._pages: list[PageData] = []
        self._flow_graph: list[FlowEdge] = []
        self._page_index = 0
        self._error_count = 0

    # ── Public API ────────────────────────────────────────────────────────

    async def crawl(self) -> CrawlResult:
        cfg = self._crawler_config
        target_url: str = self._config.get("target_url", "")
        start_time = time.monotonic()

        page = await self._context.new_page()

        # Set bearer token header if configured
        if cfg.auth_config.type == "bearer" and cfg.auth_config.bearer_token:
            await page.set_extra_http_headers(
                {"Authorization": f"Bearer {cfg.auth_config.bearer_token}"}
            )

        try:
            await self.handle_authentication(page, cfg.auth_config, target_url)
        except Exception as exc:
            logger.warning("auth_failed", error=str(exc))

        self._queue.append((target_url, 0, None))

        while self._queue and len(self._pages) < cfg.max_pages:
            url, depth, referrer = self._queue.popleft()

            # Normalise and deduplicate
            url = self._normalise_url(url)
            if not url or url in self._visited:
                continue
            if depth > cfg.max_depth:
                continue
            if self._is_excluded(url, cfg.exclude_patterns):
                continue
            if cfg.same_origin_only and not self._same_origin(url, target_url):
                continue
            if cfg.include_patterns and not self._is_included(url, cfg.include_patterns):
                continue

            try:
                page_data = await self._visit_page(page, url, depth)
                self._visited.add(url)
                self._pages.append(page_data)

                if referrer:
                    self._flow_graph.append(
                        FlowEdge(from_url=referrer, to_url=url, trigger_action="navigate")
                    )

                # Save to DB every 10 pages
                if len(self._pages) % 10 == 0:
                    await self._persist_page_batch()

                # Enqueue new links
                if depth < cfg.max_depth:
                    for link in page_data.links:
                        if link not in self._visited:
                            self._queue.append((link, depth + 1, url))

                await asyncio.sleep(cfg.interaction_delay_ms / 1000)

            except Exception as exc:
                self._error_count += 1
                logger.warning("page_visit_error", url=url, depth=depth, error=str(exc))

        # Persist any remaining pages
        await self._persist_page_batch()
        await page.close()

        duration_ms = round((time.monotonic() - start_time) * 1000)
        logger.info(
            "web_crawl_complete",
            pages=len(self._pages),
            edges=len(self._flow_graph),
            errors=self._error_count,
            duration_ms=duration_ms,
        )
        return CrawlResult(
            pages=self._pages,
            flow_graph=self._flow_graph,
            duration_ms=duration_ms,
            crawler_type="WEB",
            target_url=target_url,
            job_id=self._config.get("job_id", ""),
            project_id=self._config.get("project_id", ""),
            tenant_id=self._config.get("tenant_id", ""),
            error_count=self._error_count,
        )

    async def analyze_page(self, page: Page, url: str) -> PageData:
        """Extract structured information from the currently loaded page."""
        cfg = self._crawler_config
        t0 = time.monotonic()

        title = await page.title()

        # Parallel JS extraction
        elements_raw, forms_raw, nav_raw, signals = await asyncio.gather(
            page.evaluate(_JS_EXTRACT_ELEMENTS),
            page.evaluate(_JS_EXTRACT_FORMS),
            page.evaluate(_JS_EXTRACT_NAV),
            page.evaluate(_JS_CLASSIFY_PAGE),
        )

        elements = [
            UIElement(
                tag=e.get("tag", ""),
                type=e.get("type"),
                id=e.get("id"),
                name=e.get("name"),
                placeholder=e.get("placeholder"),
                label=e.get("label"),
                href=e.get("href"),
                text=e.get("text"),
                role=e.get("role"),
                aria_label=e.get("aria_label"),
                is_interactive=e.get("is_interactive", True),
                selector=e.get("selector"),
            )
            for e in (elements_raw or [])
        ]

        forms = [
            FormData(
                form_id=f.get("form_id"),
                action_url=f.get("action_url"),
                method=f.get("method", "POST"),
                fields=[
                    UIElement(
                        tag=fld.get("tag", "input"),
                        type=fld.get("type"),
                        id=fld.get("id"),
                        name=fld.get("name"),
                        placeholder=fld.get("placeholder"),
                        label=fld.get("label"),
                        is_interactive=True,
                    )
                    for fld in f.get("fields", [])
                ],
                submit_selector=f.get("submit_selector"),
                submit_text=f.get("submit_text"),
            )
            for f in (forms_raw or [])
        ]

        page_type = _classify_page_type(signals or {})

        # Extract all internal links
        links = await self._extract_links(page, self._config.get("target_url", ""))

        load_ms = round((time.monotonic() - t0) * 1000)

        return PageData(
            url=url,
            title=title,
            page_type=page_type,
            ui_elements=elements,
            forms=forms,
            links=links,
            navigation_items=[n for n in (nav_raw or []) if n],
            page_load_time_ms=load_ms,
        )

    async def handle_authentication(
        self, page: Page, auth_config: AuthConfig, target_url: str
    ) -> None:
        """Authenticate before starting the crawl."""
        if auth_config.type == "none":
            return

        if auth_config.type == "cookie":
            await self._context.add_cookies(auth_config.cookies)
            logger.info("auth_cookies_set", count=len(auth_config.cookies))
            return

        if auth_config.type == "basic":
            await self._context.set_http_credentials(
                {"username": auth_config.username, "password": auth_config.password}
            )
            logger.info("auth_basic_set")
            return

        if auth_config.type == "bearer":
            # Header already set before this call; nothing else needed here
            logger.info("auth_bearer_set")
            return

        if auth_config.type == "form":
            login_url = auth_config.login_url or urljoin(target_url, "/login")
            try:
                await page.goto(
                    login_url,
                    wait_until="networkidle",
                    timeout=auth_config.wait_for_selector and 30_000 or 30_000,
                )
            except Exception:
                await page.goto(login_url, timeout=30_000)

            # Fill credentials
            await page.fill(auth_config.username_selector, auth_config.username)
            await page.fill(auth_config.password_selector, auth_config.password)
            await page.click(auth_config.submit_selector)

            try:
                await page.wait_for_load_state("networkidle", timeout=30_000)
            except Exception:
                pass

            # Validate success
            if auth_config.post_login_selector:
                try:
                    await page.wait_for_selector(auth_config.post_login_selector, timeout=10_000)
                except Exception:
                    raise RuntimeError(
                        f"Auth appeared to fail: post-login selector "
                        f"'{auth_config.post_login_selector}' not found."
                    )

            if auth_config.post_login_url_pattern:
                current = page.url
                if not re.search(auth_config.post_login_url_pattern, current):
                    raise RuntimeError(
                        f"Auth appeared to fail: URL '{current}' does not match "
                        f"expected pattern '{auth_config.post_login_url_pattern}'."
                    )

            logger.info("auth_form_success", final_url=page.url)

    # ── Private helpers ───────────────────────────────────────────────────

    async def _visit_page(self, page: Page, url: str, depth: int) -> PageData:
        self._page_index += 1
        cfg = self._crawler_config

        try:
            await page.goto(
                url,
                wait_until="networkidle",
                timeout=cfg.page_load_timeout,
            )
        except Exception:
            # Fallback: wait for domcontentloaded only
            await page.goto(url, wait_until="domcontentloaded", timeout=cfg.page_load_timeout)

        # Wait for configurable selector before extracting
        if cfg.wait_for_selector and cfg.wait_for_selector != "body":
            try:
                await page.wait_for_selector(cfg.wait_for_selector, timeout=10_000)
            except Exception:
                pass

        actual_url = page.url
        page_data = await self.analyze_page(page, actual_url)
        page_data.depth = depth

        # Screenshot
        page_data.screenshot_blob_url = await self._take_screenshot(
            page, self._config.get("tenant_id", ""), self._page_index
        )

        # Stable hash of element structure for dedup
        elem_sig = "|".join(f"{e.tag}:{e.name or e.id or ''}" for e in page_data.ui_elements[:30])
        page_data.page_hash = hashlib.sha256(elem_sig.encode()).hexdigest()

        logger.debug(
            "page_visited",
            url=actual_url,
            depth=depth,
            page_type=page_data.page_type.value,
            elements=len(page_data.ui_elements),
        )
        return page_data

    async def _extract_links(self, page: Page, base_url: str) -> list[str]:
        """Extract all navigable internal links from the current page."""
        cfg = self._crawler_config
        base_origin = urlparse(base_url).netloc

        try:
            hrefs: list[str] = await page.evaluate("""() =>
                Array.from(document.querySelectorAll('a[href]'))
                    .map(a => a.href)
                    .filter(h => h &&
                        !h.startsWith('javascript:') &&
                        !h.startsWith('mailto:') &&
                        !h.startsWith('tel:') &&
                        !h.match(/\\.(pdf|zip|docx?|xlsx?|png|jpe?g|gif|svg|ico|woff2?)$/i)
                    )
            """)
        except Exception:
            return []

        links = []
        seen: set[str] = set()
        for href in hrefs:
            clean = href.split("#")[0].rstrip("/") or href.split("#")[0]
            if not clean:
                continue
            parsed = urlparse(clean)
            if cfg.same_origin_only and parsed.netloc and parsed.netloc != base_origin:
                continue
            # Make absolute
            if not parsed.scheme:
                clean = urljoin(base_url, clean)
            if clean not in seen:
                seen.add(clean)
                links.append(clean)

        return links

    async def _persist_page_batch(self) -> None:
        """Persist un-saved pages to SQL DB."""
        crawl_job_id = self._config.get("job_id", "")
        tenant_id = self._config.get("tenant_id", "")
        if not crawl_job_id or not tenant_id:
            return
        # Persist all pages (the base method is idempotent on page_hash + crawl_job_id)
        for page_data in self._pages:
            await self._save_crawl_page(page_data, crawl_job_id, tenant_id)

    @staticmethod
    def _normalise_url(url: str) -> str:
        parsed = urlparse(url)
        if not parsed.scheme:
            return ""
        # Drop fragment
        return parsed._replace(fragment="").geturl()

    @staticmethod
    def _same_origin(url: str, base_url: str) -> bool:
        return urlparse(url).netloc == urlparse(base_url).netloc

    @staticmethod
    def _is_excluded(url: str, patterns: list[str]) -> bool:
        for pattern in patterns:
            try:
                if re.search(pattern.replace("*", ".*"), url, re.IGNORECASE):
                    return True
            except re.error:
                pass
        return False

    @staticmethod
    def _is_included(url: str, patterns: list[str]) -> bool:
        for pattern in patterns:
            try:
                if re.search(pattern.replace("*", ".*"), url, re.IGNORECASE):
                    return True
            except re.error:
                pass
        return False


# Backward-compat alias — the worker imports WebCrawler
WebCrawler = WebUICrawler
