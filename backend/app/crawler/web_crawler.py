"""
Generic web UI crawler.

Uses BFS page traversal starting from a seed URL.
Captures screenshots and DOM structure for each visited page.
"""

from __future__ import annotations

import asyncio
import re
from collections import deque
from typing import Any
from urllib.parse import urljoin, urlparse

import structlog
from playwright.async_api import BrowserContext, Page

from app.crawler.base import BaseCrawler, CrawlFlow, CrawlMap, CrawlStep

logger = structlog.get_logger(__name__)


class WebCrawler(BaseCrawler):
    def __init__(self, context: BrowserContext, job_config: dict[str, Any]) -> None:
        super().__init__(context, job_config)
        self._visited: set[str] = set()
        self._queue: deque[tuple[str, int]] = deque()  # (url, depth)
        self._flows: list[CrawlFlow] = []
        self._page_index = 0

    async def run(self) -> CrawlMap:
        target_url: str = self._config.get("target_url", "")
        max_pages: int = self._config.get("max_pages", 100)
        max_depth: int = self._config.get("max_depth", 5)
        exclude_patterns: list[str] = self._config.get("exclude_patterns", [])

        page = await self._context.new_page()
        await self._authenticate(page)
        self._queue.append((target_url, 0))

        while self._queue and len(self._visited) < max_pages:
            url, depth = self._queue.popleft()
            if url in self._visited or depth > max_depth:
                continue
            if self._is_excluded(url, exclude_patterns):
                continue

            try:
                flow = await self._visit_page(page, url, depth)
                if flow:
                    self._flows.append(flow)
                self._visited.add(url)

                if depth < max_depth:
                    new_links = await self._extract_links(page, target_url)
                    for link in new_links:
                        if link not in self._visited:
                            self._queue.append((link, depth + 1))

                await asyncio.sleep(self._config.get("interaction_delay_ms", 500) / 1000)
            except Exception as exc:
                logger.warning("page_crawl_error", url=url, error=str(exc))

        await page.close()
        logger.info(
            "web_crawl_complete",
            pages_visited=len(self._visited),
            flows_found=len(self._flows),
        )
        return CrawlMap(
            job_id=self._config.get("job_id", ""),
            project_id=self._config.get("project_id", ""),
            tenant_id=self._config.get("tenant_id", ""),
            crawler_type="WEB",
            target_url=target_url,
            pages_visited=len(self._visited),
            flows=self._flows,
        )

    async def _authenticate(self, page: Page) -> None:
        auth = self._config.get("auth_config", {})
        auth_type = auth.get("type", "none")

        if auth_type == "none":
            return

        if auth_type == "form":
            creds = self._config.get("_resolved_credentials", {})
            login_url = self._config.get("login_url") or urljoin(
                self._config.get("target_url", ""), "/login"
            )
            await page.goto(login_url, timeout=30000)
            await page.wait_for_load_state("networkidle")

            username_sel = creds.get("username_selector", "[name=username],[name=email],[id=email]")
            password_sel = creds.get("password_selector", "[type=password]")
            submit_sel = creds.get("submit_selector", "button[type=submit]")

            await page.fill(username_sel, creds.get("username", ""))
            await page.fill(password_sel, creds.get("password", ""))
            await page.click(submit_sel)
            await page.wait_for_load_state("networkidle")
            logger.info("web_crawler_authenticated", auth_type=auth_type)

        elif auth_type == "cookie":
            cookies = self._config.get("_resolved_credentials", {}).get("cookies", [])
            await self._context.add_cookies(cookies)

        elif auth_type == "basic":
            creds = self._config.get("_resolved_credentials", {})
            await self._context.set_http_credentials({
                "username": creds.get("username", ""),
                "password": creds.get("password", ""),
            })

    async def _visit_page(self, page: Page, url: str, depth: int) -> CrawlFlow | None:
        self._page_index += 1
        timeout = self._config.get("page_load_timeout_ms", 30000)

        await page.goto(url, timeout=timeout, wait_until="networkidle")
        actual_url = page.url
        title = await page.title()

        screenshot_uri = await self._take_screenshot(
            page, None, self._config.get("tenant_id", ""), self._page_index
        )

        interactive_elements = await page.evaluate("""() => {
            const elements = document.querySelectorAll(
                'a[href], button, input, select, textarea, [role="button"], [role="link"]'
            );
            return Array.from(elements).slice(0, 50).map(el => ({
                tag: el.tagName.toLowerCase(),
                type: el.type || null,
                label: el.ariaLabel || el.textContent?.trim().slice(0, 80) || null,
                href: el.href || null,
                name: el.name || el.id || null,
                role: el.role || null,
            }));
        }""")

        steps = [
            CrawlStep(
                step=1,
                action="navigate",
                url=actual_url,
                expected_state=f"Page '{title}' loaded",
            )
        ]

        flow = CrawlFlow(
            flow_id=f"flow-{self._page_index:04d}",
            name=title or actual_url,
            steps=steps,
            screenshot_uris=[screenshot_uri] if screenshot_uri else [],
        )
        return flow

    async def _extract_links(self, page: Page, base_url: str) -> list[str]:
        same_origin_only = self._config.get("same_origin_only", True)
        base_origin = urlparse(base_url).netloc

        hrefs: list[str] = await page.evaluate("""() =>
            Array.from(document.querySelectorAll('a[href]'))
                .map(a => a.href)
                .filter(h => h && !h.startsWith('javascript:') && !h.startsWith('mailto:'))
        """)

        links = []
        for href in hrefs:
            parsed = urlparse(href)
            if same_origin_only and parsed.netloc != base_origin:
                continue
            # Strip fragment
            clean = href.split("#")[0]
            if clean:
                links.append(clean)
        return list(set(links))

    def _is_excluded(self, url: str, patterns: list[str]) -> bool:
        for pattern in patterns:
            if re.search(pattern.replace("*", ".*"), url):
                return True
        return False
