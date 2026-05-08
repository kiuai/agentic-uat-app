"""
SAP Fiori Launchpad crawler.

Enumerates tile groups and tiles, launches each app, maps available views
and toolbar actions, then navigates back to the launchpad.
"""

from __future__ import annotations

from typing import Any

import structlog
from playwright.async_api import BrowserContext, Page

from app.crawler.base import BaseCrawler, CrawlFlow, CrawlMap, CrawlStep

logger = structlog.get_logger(__name__)


class SAPFioriCrawler(BaseCrawler):
    def __init__(self, context: BrowserContext, job_config: dict[str, Any]) -> None:
        super().__init__(context, job_config)
        self._flows: list[CrawlFlow] = []
        self._page_index = 0

    async def run(self) -> CrawlMap:
        launchpad_url: str = self._config.get("launchpad_url", "")
        tile_groups_filter: list[str] = self._config.get("tile_groups", [])

        page = await self._context.new_page()
        await self._authenticate(page, launchpad_url)

        # Wait for Fiori Launchpad shell to render
        await page.wait_for_selector(".sapUshellTile, .sapUshellTileContainer", timeout=60000)
        logger.info("sap_fiori_launchpad_loaded", url=launchpad_url)

        tile_groups = await self._enumerate_tile_groups(page, tile_groups_filter)

        for group_name, tiles in tile_groups.items():
            for tile in tiles:
                try:
                    flow = await self._explore_tile(page, tile, launchpad_url)
                    if flow:
                        self._flows.append(flow)
                except Exception as exc:
                    logger.warning(
                        "sap_tile_explore_error",
                        tile=tile.get("title"),
                        error=str(exc),
                    )
                    # Navigate back to launchpad on error
                    try:
                        await page.goto(launchpad_url, timeout=30000)
                        await page.wait_for_selector(".sapUshellTile", timeout=30000)
                    except Exception:
                        pass

        await page.close()
        return CrawlMap(
            job_id=self._config.get("job_id", ""),
            project_id=self._config.get("project_id", ""),
            tenant_id=self._config.get("tenant_id", ""),
            crawler_type="SAP_FIORI",
            target_url=launchpad_url,
            pages_visited=self._page_index,
            flows=self._flows,
            metadata={"tile_groups_explored": list(tile_groups.keys())},
        )

    async def _authenticate(self, page: Page, launchpad_url: str) -> None:
        auth = self._config.get("auth_config", {})
        if auth.get("type") == "basic":
            creds = self._config.get("_resolved_credentials", {})
            await self._context.set_http_credentials({
                "username": creds.get("username", ""),
                "password": creds.get("password", ""),
            })

        await page.goto(launchpad_url, timeout=60000, wait_until="networkidle")

        # Handle SAP form-based login if redirected
        if "/sap/bc/ui5_ui5/ui2/ushell" not in page.url and auth.get("type") == "form":
            creds = self._config.get("_resolved_credentials", {})
            await page.fill("[name=sap-user],[id=USERNAME_FIELD-inner]", creds.get("username", ""))
            await page.fill("[name=sap-password],[id=PASSWORD_FIELD-inner]", creds.get("password", ""))
            await page.click("[id=LOGIN_LINK],[id=LOGON_BUTTON]")
            await page.wait_for_load_state("networkidle", timeout=30000)

        logger.info("sap_fiori_authenticated")

    async def _enumerate_tile_groups(
        self, page: Page, filter_groups: list[str]
    ) -> dict[str, list[dict[str, Any]]]:
        groups: dict[str, list[dict[str, Any]]] = {}

        group_headers = await page.query_selector_all(
            ".sapUshellTileContainerHeader, .sapUshellDashboardGroupsContainerItem-header"
        )

        for header in group_headers:
            group_name = await header.inner_text()
            group_name = group_name.strip()

            if filter_groups and group_name not in filter_groups:
                continue

            # Get the parent container and find its tiles
            container = await header.evaluate_handle(
                "el => el.closest('.sapUshellTileContainerContent, .sapUshellDashboardGroupsContainerItem')"
            )
            tile_elements = await container.query_selector_all(".sapUshellTile")

            tiles = []
            for tile_el in tile_elements:
                title_el = await tile_el.query_selector(".sapUshellTileTitle, .sapUshellPlusTileTitle")
                title = await title_el.inner_text() if title_el else "Unknown"
                tiles.append({"title": title.strip(), "element": tile_el})

            groups[group_name] = tiles
            logger.debug("sap_tile_group_found", group=group_name, tile_count=len(tiles))

        return groups

    async def _explore_tile(
        self, page: Page, tile: dict[str, Any], launchpad_url: str
    ) -> CrawlFlow | None:
        self._page_index += 1
        tile_title = tile.get("title", f"Tile-{self._page_index}")
        tile_el = tile.get("element")

        await tile_el.click()
        await page.wait_for_load_state("networkidle", timeout=30000)
        app_url = page.url
        app_title = await page.title()

        screenshot_uri = await self._take_screenshot(
            page, None, self._config.get("tenant_id", ""), self._page_index
        )

        # Discover toolbar actions
        toolbar_actions = await page.evaluate("""() => {
            const buttons = document.querySelectorAll('.sapMBtn, .sapMToolbarButton');
            return Array.from(buttons).slice(0, 20).map(b => ({
                label: b.ariaLabel || b.textContent?.trim() || '',
                id: b.id || null
            }));
        }""")

        # Discover filter bar fields (SAP Smart FilterBar)
        filter_fields = await page.evaluate("""() => {
            const labels = document.querySelectorAll('.sapUiCompFilterBar .sapMLabel, .sapUiSFBFilter .sapMLabel');
            return Array.from(labels).slice(0, 20).map(l => l.textContent?.trim());
        }""")

        steps = [
            CrawlStep(step=1, action="navigate", url=launchpad_url, expected_state="Launchpad loaded"),
            CrawlStep(step=2, action="click", selector=f".sapUshellTile[title='{tile_title}']", expected_state=f"App '{app_title}' opened"),
        ]

        flow = CrawlFlow(
            flow_id=f"sap-flow-{self._page_index:04d}",
            name=f"SAP: {tile_title}",
            steps=steps,
            screenshot_uris=[screenshot_uri] if screenshot_uri else [],
        )

        # Navigate back to launchpad
        await page.goto(launchpad_url, timeout=30000)
        await page.wait_for_selector(".sapUshellTile", timeout=30000)

        logger.info("sap_tile_explored", tile=tile_title, app_url=app_url)
        return flow
