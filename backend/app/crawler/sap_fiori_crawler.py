"""
SAP Fiori Launchpad crawler.

Strategy
--------
1. Navigate to Fiori Launchpad; authenticate via SAP form login
2. Enumerate tile groups → tiles (filtered by config.tile_groups)
3. For each tile: launch app, detect view type, explore secondary views
   (list → detail, detail → edit form, list → create form)
4. Extract SAP UI5 control types via JS + standard page analysis
5. Return CrawlResult with SAP-specific metadata

SAP UI5 controls detected via CSS classes (no UI5 API access needed):
  .sapMTable / .sapUiTable  → LIST
  .sapMForm / .sapUiForm    → FORM
  .sapMObjectHeader         → DETAIL
  .sapMFCL                  → DETAIL (flexible column layout)
  .sapUshellAnalyticalCard  → DASHBOARD
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import Any

import structlog
from playwright.async_api import BrowserContext, ElementHandle, Page

from app.crawler.base import (
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
# SAP-specific data
# ---------------------------------------------------------------------------


@dataclass
class TileInfo:
    tile_id: str
    title: str
    subtitle: str = ""
    app_id: str = ""
    semantic_object: str = ""
    action: str = ""
    group_name: str = ""


@dataclass
class SAPFieldInfo:
    label: str
    field_type: str = "input"
    is_mandatory: bool = False
    has_value_help: bool = False
    max_length: int | None = None
    selector: str = ""


# ---------------------------------------------------------------------------
# JS snippets
# ---------------------------------------------------------------------------

_JS_GET_TILES = """() => {
    const tiles = [];
    document.querySelectorAll('.sapUshellTile, .sapUshellPlusTile').forEach((el, idx) => {
        const titleEl = el.querySelector('.sapUshellTileTitle, .sapUshellPlusTileTitle, .sapUshellTileTitle');
        const subEl = el.querySelector('.sapUshellTileSubtitle, .sapUshellPlusTileSubtitle');
        const appId = el.getAttribute('data-help-id') ||
                      el.querySelector('[data-help-id]')?.getAttribute('data-help-id') || '';
        tiles.push({
            index: idx,
            title: titleEl?.textContent?.trim() || ('Tile ' + idx),
            subtitle: subEl?.textContent?.trim() || '',
            app_id: appId,
        });
    });
    return tiles;
}"""

_JS_GET_TILE_GROUPS = """() => {
    const groups = {};
    document.querySelectorAll(
        '.sapUshellTileContainerContent, .sapUshellDashboardGroupsContainerItem'
    ).forEach(container => {
        const hdr = container.querySelector(
            '.sapUshellTileContainerHeader, ' +
            '.sapUshellDashboardGroupsContainerItem-header'
        );
        const name = hdr?.textContent?.trim() || 'Default';
        const tileEls = container.querySelectorAll('.sapUshellTile, .sapUshellPlusTile');
        const tiles = Array.from(tileEls).map((el, idx) => {
            const t = el.querySelector('.sapUshellTileTitle,.sapUshellPlusTileTitle');
            const s = el.querySelector('.sapUshellTileSubtitle,.sapUshellPlusTileSubtitle');
            return {
                index: idx,
                title: t?.textContent?.trim() || 'Tile ' + idx,
                subtitle: s?.textContent?.trim() || '',
            };
        });
        if (tiles.length) groups[name] = tiles;
    });
    return groups;
}"""

_JS_DETECT_SAP_CONTROLS = """() => {
    return {
        hasMTable:    !!document.querySelector('.sapMTable, .sapMList'),
        hasUiTable:   !!document.querySelector('.sapUiTable'),
        hasMForm:     !!document.querySelector('.sapMForm, .sapUiForm'),
        hasObjectHdr: !!document.querySelector('.sapMObjectHeader, .sapMObjectListItem'),
        hasFCL:       !!document.querySelector('.sapMFCL, .sapFCL'),
        hasAnalytics: !!document.querySelector('.sapUshellAnalyticalCard, canvas, .sapSuiteUiCommonsInteractiveChart'),
        hasFilterBar: !!document.querySelector('.sapUiCompFilterBar, .sapUiSFBFilter'),
        buttonTexts: Array.from(document.querySelectorAll('.sapMBtn')).slice(0,20).map(b =>
            b.querySelector('.sapMBtnInner')?.textContent?.trim() || b.ariaLabel || ''
        ).filter(Boolean),
        smartFields: Array.from(document.querySelectorAll('.sapMForm .sapMLabel, .sapUiForm .sapMLabel')).slice(0,30).map(l =>
            l.textContent?.trim()
        ).filter(Boolean),
    };
}"""

_JS_EXTRACT_SAP_FIELDS = """() => {
    const results = [];
    const containers = document.querySelectorAll(
        '.sapMFormGroupContent, .sapUiFormContainerContent, .sapMFormElement'
    );
    containers.forEach(container => {
        const label = container.querySelector('.sapMLabel, .sapUiFormLabel');
        const input = container.querySelector('input, select, textarea, .sapMInputBase');
        if (!label) return;
        const isMandatory = label.classList.contains('sapMLabelRequired') ||
                            !!label.querySelector('.sapMLabelColonAndRequired');
        const hasVH = !!container.querySelector('.sapFRBtnEdit, [data-sap-ui-sh-icon],.sapMInputBaseIconContainer');
        const maxLen = input?.maxLength > 0 ? input.maxLength : null;
        results.push({
            label: label.textContent?.trim().replace(':', ''),
            field_type: input?.tagName?.toLowerCase() || 'input',
            input_type: input?.type || 'text',
            is_mandatory: isMandatory,
            has_value_help: hasVH,
            max_length: maxLen,
            selector: input?.id ? '#' + input.id :
                       (input?.name ? 'input[name="' + input.name + '"]' : '.sapMInputBase'),
        });
    });
    return results;
}"""


def _classify_sap_page(controls: dict[str, Any]) -> PageType:
    if controls.get("hasFCL") or (controls.get("hasMTable") and controls.get("hasObjectHdr")):
        return PageType.DETAIL
    if controls.get("hasMForm") or controls.get("hasMForm"):
        if not controls.get("hasMTable"):
            return PageType.FORM
    if controls.get("hasMTable") or controls.get("hasUiTable"):
        return PageType.LIST
    if controls.get("hasObjectHdr"):
        return PageType.DETAIL
    if controls.get("hasAnalytics"):
        return PageType.DASHBOARD
    return PageType.UNKNOWN


class SAPFioriCrawler(BaseCrawler):
    """SAP Fiori Launchpad crawler with UI5 control detection."""

    def __init__(self, context: BrowserContext, job_config: dict[str, Any]) -> None:
        super().__init__(context, job_config)
        self._pages: list[PageData] = []
        self._flow_graph: list[FlowEdge] = []
        self._page_index = 0
        self._error_count = 0

    # ── Public API ────────────────────────────────────────────────────────

    async def crawl(self) -> CrawlResult:
        cfg = self._crawler_config
        launchpad_url: str = self._config.get("launchpad_url", "")
        start_time = time.monotonic()

        page = await self._context.new_page()

        # Authenticate
        try:
            await self._authenticate_sap(page, launchpad_url)
        except Exception as exc:
            logger.error("sap_auth_failed", error=str(exc))
            await page.close()
            return CrawlResult(
                crawler_type="SAP_FIORI",
                target_url=launchpad_url,
                job_id=self._config.get("job_id", ""),
                project_id=self._config.get("project_id", ""),
                tenant_id=self._config.get("tenant_id", ""),
                error_count=1,
                metadata={"error": f"Authentication failed: {exc}"},
            )

        # Wait for Fiori shell
        try:
            await page.wait_for_selector(
                ".sapUshellTile, .sapUshellTileContainer, .sapUshellPlusTile",
                timeout=60_000,
            )
        except Exception:
            logger.warning("fiori_launchpad_not_detected", url=page.url)

        logger.info("fiori_launchpad_loaded", url=launchpad_url)

        # Add launchpad as first page
        lp_data = await self.analyze_page(page, page.url)
        lp_data.sap_metadata["is_launchpad"] = True
        self._pages.append(lp_data)

        # Discover tile groups
        tile_groups = await self._enumerate_tile_groups(page, cfg.tile_groups)
        logger.info("fiori_tile_groups", groups=list(tile_groups.keys()))

        tile_count = 0
        for group_name, tiles in tile_groups.items():
            for tile in tiles:
                if tile_count >= cfg.max_pages - 1:
                    break
                try:
                    pages = await self._explore_tile_app(page, tile, launchpad_url, group_name)
                    for pd in pages:
                        self._pages.append(pd)
                        if len(self._pages) % 5 == 0:
                            await self._persist_page_batch()
                    tile_count += 1
                except Exception as exc:
                    self._error_count += 1
                    logger.warning(
                        "sap_tile_error", tile=tile.title, error=str(exc)
                    )
                    try:
                        await page.goto(launchpad_url, timeout=30_000)
                        await page.wait_for_selector(".sapUshellTile", timeout=30_000)
                    except Exception:
                        pass

        await self._persist_page_batch()
        await page.close()

        duration_ms = round((time.monotonic() - start_time) * 1000)
        logger.info(
            "fiori_crawl_complete",
            pages=len(self._pages),
            errors=self._error_count,
            duration_ms=duration_ms,
        )
        return CrawlResult(
            pages=self._pages,
            flow_graph=self._flow_graph,
            duration_ms=duration_ms,
            crawler_type="SAP_FIORI",
            target_url=launchpad_url,
            job_id=self._config.get("job_id", ""),
            project_id=self._config.get("project_id", ""),
            tenant_id=self._config.get("tenant_id", ""),
            error_count=self._error_count,
            metadata={"tile_groups_explored": list(tile_groups.keys())},
        )

    async def analyze_page(self, page: Page, url: str) -> PageData:
        """Generic page analysis — delegates to analyze_fiori_app for app pages."""
        return await self._analyze_generic(page, url, {})

    async def analyze_fiori_app(
        self, page: Page, url: str, tile_info: TileInfo
    ) -> PageData:
        """SAP Fiori-specific page analysis with UI5 control detection."""
        try:
            controls: dict[str, Any] = await page.evaluate(_JS_DETECT_SAP_CONTROLS)
        except Exception:
            controls = {}

        page_type = _classify_sap_page(controls)
        title = await page.title()

        # Extract SAP form fields
        sap_fields: list[SAPFieldInfo] = []
        try:
            raw_fields = await page.evaluate(_JS_EXTRACT_SAP_FIELDS)
            sap_fields = [
                SAPFieldInfo(
                    label=f.get("label", ""),
                    field_type=f.get("input_type") or f.get("field_type", "input"),
                    is_mandatory=f.get("is_mandatory", False),
                    has_value_help=f.get("has_value_help", False),
                    max_length=f.get("max_length"),
                    selector=f.get("selector", ""),
                )
                for f in (raw_fields or [])
            ]
        except Exception:
            pass

        # Map to generic UIElements
        elements: list[UIElement] = [
            UIElement(
                tag="input",
                type=sf.field_type,
                label=sf.label,
                selector=sf.selector,
                is_interactive=True,
                sap_control_type="SmartField",
            )
            for sf in sap_fields
        ]

        # Add action buttons
        button_texts: list[str] = controls.get("buttonTexts", [])
        for btn_text in button_texts:
            elements.append(
                UIElement(
                    tag="button",
                    text=btn_text,
                    selector=f'.sapMBtn:has-text("{btn_text}")',
                    is_interactive=True,
                    sap_control_type="Button",
                )
            )

        # Build SAP-specific form if FORM page
        forms: list[FormData] = []
        if page_type == PageType.FORM and sap_fields:
            save_btn = next(
                (t for t in button_texts if t.lower() in ("save", "create", "ok", "post")),
                None,
            )
            forms.append(
                FormData(
                    form_id="sap-smart-form",
                    fields=[
                        UIElement(
                            tag="input",
                            label=sf.label,
                            selector=sf.selector,
                            is_interactive=True,
                        )
                        for sf in sap_fields
                    ],
                    submit_text=save_btn,
                    submit_selector=f'.sapMBtn:has-text("{save_btn}")' if save_btn else None,
                )
            )

        sap_meta = {
            "app_id": tile_info.app_id,
            "semantic_object": tile_info.semantic_object,
            "action": tile_info.action,
            "group_name": tile_info.group_name,
            "control_types": {
                "table": controls.get("hasMTable") or controls.get("hasUiTable"),
                "form": controls.get("hasMForm"),
                "object_header": controls.get("hasObjectHdr"),
                "flexible_column": controls.get("hasFCL"),
                "filter_bar": controls.get("hasFilterBar"),
                "analytics": controls.get("hasAnalytics"),
            },
            "field_count": len(sap_fields),
            "mandatory_fields": [sf.label for sf in sap_fields if sf.is_mandatory],
            "value_help_fields": [sf.label for sf in sap_fields if sf.has_value_help],
        }

        return PageData(
            url=url,
            title=title,
            page_type=page_type,
            ui_elements=elements,
            forms=forms,
            links=[],
            navigation_items=[],
            sap_metadata=sap_meta,
        )

    async def detect_sap_field_properties(
        self, page: Page, field_selector: str
    ) -> dict[str, Any]:
        """
        For a specific SAP field, read UI5 control metadata via JS evaluation.
        Returns field properties dict.
        """
        try:
            props: dict[str, Any] = await page.evaluate(
                """(selector) => {
                    const el = document.querySelector(selector);
                    if (!el) return {};

                    // Try to read UI5 control instance
                    let ctrl = null;
                    try {
                        const id = el.id || el.closest('[data-sap-ui]')?.id;
                        if (id && window.sap && window.sap.ui) {
                            ctrl = sap.ui.getCore().byId(id);
                        }
                    } catch(e) {}

                    const isMandatory = el.getAttribute('aria-required') === 'true' ||
                                        !!el.closest('.sapMLabelRequired');
                    const hasVH = !!el.closest('.sapMInputBase')?.querySelector(
                        '.sapFRBtnEdit, .sapMInputBaseIconContainer'
                    );

                    return {
                        label: el.getAttribute('aria-label') ||
                               document.querySelector('label[for="' + el.id + '"]')?.textContent?.trim() || '',
                        field_type: el.type || el.tagName.toLowerCase(),
                        is_mandatory: isMandatory,
                        has_value_help: hasVH,
                        max_length: el.maxLength > 0 ? el.maxLength : null,
                        placeholder: el.placeholder || null,
                        // UI5 metadata if available
                        ui5_control_type: ctrl?.getMetadata?.()?.getName?.() || null,
                    };
                }""",
                field_selector,
            )
            return props
        except Exception as exc:
            logger.warning("sap_field_detect_failed", selector=field_selector, error=str(exc))
            return {}

    # ── Private helpers ───────────────────────────────────────────────────

    async def _authenticate_sap(self, page: Page, launchpad_url: str) -> None:
        cfg = self._crawler_config
        auth = cfg.auth_config

        if auth.type == "basic":
            await self._context.set_http_credentials(
                {"username": auth.username, "password": auth.password}
            )

        await page.goto(launchpad_url, timeout=60_000, wait_until="networkidle")

        # Detect if we've been redirected to a login page
        login_detected = await page.evaluate("""() =>
            !!(document.querySelector('[name=sap-user],[id*=USERNAME_FIELD],[name=j_username]'))
        """)

        if login_detected and auth.type in ("form", "basic"):
            logger.info("sap_login_form_detected")
            # Try common SAP login field selectors
            username_selectors = [
                "[name=sap-user]",
                "[id*=USERNAME_FIELD-inner]",
                "[name=j_username]",
                "#logonuidfield",
                "input[autocomplete=username]",
            ]
            password_selectors = [
                "[name=sap-password]",
                "[id*=PASSWORD_FIELD-inner]",
                "[name=j_password]",
                "#logonpassfield",
                "[type=password]",
            ]
            submit_selectors = [
                "[id=LOGIN_LINK]",
                "[id=LOGON_BUTTON]",
                "button[type=submit]",
                "#lginbut",
            ]

            filled = False
            for sel in username_selectors:
                try:
                    await page.fill(sel, auth.username, timeout=3_000)
                    filled = True
                    break
                except Exception:
                    pass
            if not filled:
                raise RuntimeError("Could not find SAP username field.")

            for sel in password_selectors:
                try:
                    await page.fill(sel, auth.password, timeout=3_000)
                    break
                except Exception:
                    pass

            for sel in submit_selectors:
                try:
                    await page.click(sel, timeout=3_000)
                    break
                except Exception:
                    pass

            try:
                await page.wait_for_load_state("networkidle", timeout=30_000)
            except Exception:
                pass

        logger.info("sap_auth_complete", final_url=page.url)

    async def _enumerate_tile_groups(
        self, page: Page, filter_groups: list[str]
    ) -> dict[str, list[TileInfo]]:
        groups: dict[str, list[TileInfo]] = {}

        try:
            raw_groups: dict[str, list[dict]] = await page.evaluate(_JS_GET_TILE_GROUPS)
        except Exception:
            # Fallback: flat tile list
            try:
                raw_tiles: list[dict] = await page.evaluate(_JS_GET_TILES)
                raw_groups = {"Default": raw_tiles}
            except Exception:
                return {}

        for group_name, raw_tiles in raw_groups.items():
            if filter_groups and group_name not in filter_groups:
                continue
            tiles = [
                TileInfo(
                    tile_id=f"tile-{group_name}-{t.get('index', i)}",
                    title=t.get("title", f"Tile {i}"),
                    subtitle=t.get("subtitle", ""),
                    group_name=group_name,
                )
                for i, t in enumerate(raw_tiles)
            ]
            groups[group_name] = tiles

        return groups

    async def _explore_tile_app(
        self, page: Page, tile: TileInfo, launchpad_url: str, group_name: str
    ) -> list[PageData]:
        """Click a tile, explore its app views, return discovered PageData list."""
        self._page_index += 1
        discovered: list[PageData] = []

        # Find and click the tile
        tile_selectors = [
            f'.sapUshellTile:has-text("{tile.title}")',
            f'.sapUshellPlusTile:has-text("{tile.title}")',
            f'[title="{tile.title}"]',
        ]
        clicked = False
        for sel in tile_selectors:
            try:
                await page.click(sel, timeout=5_000)
                clicked = True
                break
            except Exception:
                pass

        if not clicked:
            raise RuntimeError(f"Could not click tile: {tile.title}")

        try:
            await page.wait_for_load_state("networkidle", timeout=30_000)
        except Exception:
            pass

        # Wait for app to render
        try:
            await page.wait_for_selector(
                ".sapMPage, .sapUiView, .sapUshellAppBox", timeout=20_000
            )
        except Exception:
            pass

        app_url = page.url
        main_page = await self.analyze_fiori_app(page, app_url, tile)
        main_page.depth = 1
        main_page.screenshot_blob_url = await self._take_screenshot(
            page, self._config.get("tenant_id", ""), self._page_index
        )
        discovered.append(main_page)

        self._flow_graph.append(
            FlowEdge(
                from_url=launchpad_url,
                to_url=app_url,
                trigger_element=f".sapUshellTile:has-text(\"{tile.title}\")",
                trigger_action="click",
            )
        )

        # If LIST page → try navigating to detail (click first row)
        if main_page.page_type == PageType.LIST:
            detail_pages = await self._explore_list_detail(page, app_url, tile)
            discovered.extend(detail_pages)

        # If FORM not already explored → look for Create button
        if main_page.page_type != PageType.FORM:
            create_pages = await self._explore_create_form(page, app_url, tile)
            discovered.extend(create_pages)

        # Navigate back to launchpad
        try:
            await page.goto(launchpad_url, timeout=30_000)
            await page.wait_for_selector(".sapUshellTile, .sapUshellPlusTile", timeout=30_000)
        except Exception:
            pass

        logger.info(
            "sap_tile_explored",
            tile=tile.title,
            views=len(discovered),
        )
        return discovered

    async def _explore_list_detail(
        self, page: Page, list_url: str, tile: TileInfo
    ) -> list[PageData]:
        """From a list view, click the first data row to discover detail view."""
        discovered: list[PageData] = []
        row_selectors = [
            ".sapMListItem:first-child",
            ".sapMLIB:first-child",
            ".sapUiTableRow:not(.sapUiTableColHdrTr):first-child",
            "tr.sapMListItem:first-child",
            "[role=row]:not([role=columnheader]):first-child",
        ]

        for sel in row_selectors:
            try:
                row = await page.query_selector(sel)
                if row:
                    await row.click()
                    await page.wait_for_load_state("networkidle", timeout=20_000)
                    detail_url = page.url
                    if detail_url != list_url:
                        self._page_index += 1
                        detail_tile = TileInfo(
                            tile_id=f"{tile.tile_id}-detail",
                            title=f"{tile.title} - Detail",
                            group_name=tile.group_name,
                        )
                        detail_pd = await self.analyze_fiori_app(page, detail_url, detail_tile)
                        detail_pd.depth = 2
                        detail_pd.screenshot_blob_url = await self._take_screenshot(
                            page, self._config.get("tenant_id", ""), self._page_index
                        )
                        discovered.append(detail_pd)
                        self._flow_graph.append(
                            FlowEdge(from_url=list_url, to_url=detail_url, trigger_action="click")
                        )

                        # Explore Edit form from detail
                        edit_pages = await self._explore_edit_form(page, detail_url, detail_tile)
                        discovered.extend(edit_pages)

                        # Navigate back to list
                        await page.go_back(timeout=15_000)
                    break
            except Exception:
                pass

        return discovered

    async def _explore_create_form(
        self, page: Page, source_url: str, tile: TileInfo
    ) -> list[PageData]:
        """Click Create/New button to discover create form."""
        discovered: list[PageData] = []
        create_texts = ["Create", "New", "Add", "Anlegen", "Neu"]

        for text in create_texts:
            try:
                btn = await page.query_selector(
                    f'.sapMBtn:has-text("{text}"), '
                    f'button:has-text("{text}"), '
                    f'[aria-label="{text}"]'
                )
                if btn and await btn.is_visible():
                    await btn.click()
                    await page.wait_for_load_state("networkidle", timeout=20_000)
                    form_url = page.url
                    if form_url != source_url:
                        self._page_index += 1
                        form_tile = TileInfo(
                            tile_id=f"{tile.tile_id}-create",
                            title=f"{tile.title} - Create",
                            group_name=tile.group_name,
                        )
                        form_pd = await self.analyze_fiori_app(page, form_url, form_tile)
                        form_pd.depth = 2
                        form_pd.screenshot_blob_url = await self._take_screenshot(
                            page, self._config.get("tenant_id", ""), self._page_index
                        )
                        discovered.append(form_pd)
                        self._flow_graph.append(
                            FlowEdge(from_url=source_url, to_url=form_url, trigger_action="click")
                        )
                        await page.go_back(timeout=15_000)
                    break
            except Exception:
                pass

        return discovered

    async def _explore_edit_form(
        self, page: Page, detail_url: str, tile: TileInfo
    ) -> list[PageData]:
        """From a detail page, click Edit to discover the edit form."""
        discovered: list[PageData] = []
        edit_texts = ["Edit", "Bearbeiten", "Change"]

        for text in edit_texts:
            try:
                btn = await page.query_selector(
                    f'.sapMBtn:has-text("{text}"), [aria-label="{text}"]'
                )
                if btn and await btn.is_visible():
                    await btn.click()
                    try:
                        await page.wait_for_selector(
                            ".sapMForm, .sapUiForm", timeout=10_000
                        )
                    except Exception:
                        pass
                    edit_url = page.url
                    self._page_index += 1
                    edit_tile = TileInfo(
                        tile_id=f"{tile.tile_id}-edit",
                        title=f"{tile.title} - Edit",
                        group_name=tile.group_name,
                    )
                    edit_pd = await self.analyze_fiori_app(page, edit_url, edit_tile)
                    edit_pd.depth = 3
                    edit_pd.screenshot_blob_url = await self._take_screenshot(
                        page, self._config.get("tenant_id", ""), self._page_index
                    )
                    discovered.append(edit_pd)
                    self._flow_graph.append(
                        FlowEdge(from_url=detail_url, to_url=edit_url, trigger_action="click")
                    )
                    break
            except Exception:
                pass

        return discovered

    async def _analyze_generic(
        self, page: Page, url: str, sap_meta: dict[str, Any]
    ) -> PageData:
        """Minimal analysis for launchpad and fallback pages."""
        title = await page.title()
        try:
            controls = await page.evaluate(_JS_DETECT_SAP_CONTROLS)
        except Exception:
            controls = {}

        page_type = _classify_sap_page(controls)
        return PageData(
            url=url,
            title=title,
            page_type=page_type,
            sap_metadata=sap_meta,
        )

    async def _persist_page_batch(self) -> None:
        crawl_job_id = self._config.get("job_id", "")
        tenant_id = self._config.get("tenant_id", "")
        if not crawl_job_id or not tenant_id:
            return
        for pd in self._pages:
            await self._save_crawl_page(pd, crawl_job_id, tenant_id)
