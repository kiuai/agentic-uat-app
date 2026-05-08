"""
Unit tests for crawler utility functions.

Tests cover:
- WebUICrawler._normalise_url()
- WebUICrawler._same_origin()
- WebUICrawler._is_excluded() / _is_included()
- _classify_page_type() heuristic (web)
- BaseCrawler._build_config() — AuthConfig / CrawlerConfig construction
- _classify_sap_page() heuristic (SAP Fiori)
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from app.crawler.base import PageType


# ---------------------------------------------------------------------------
# Helpers — build minimal crawler instances without a real Playwright context
# ---------------------------------------------------------------------------


def _make_web_crawler(job_config: dict | None = None):
    from app.crawler.web_crawler import WebUICrawler

    ctx = MagicMock()
    cfg = job_config or {
        "job_id": "test-job",
        "project_id": "test-project",
        "tenant_id": "test-tenant",
        "target_url": "https://example.com",
        "launchpad_url": "",
        "max_pages": 10,
        "auth_config": {"type": "none"},
        "generate_scripts": False,
    }
    return WebUICrawler(ctx, cfg)


def _make_sap_crawler(job_config: dict | None = None):
    from app.crawler.sap_fiori_crawler import SAPFioriCrawler

    ctx = MagicMock()
    cfg = job_config or {
        "job_id": "test-job",
        "project_id": "test-project",
        "tenant_id": "test-tenant",
        "target_url": "",
        "launchpad_url": "https://fiori.example.com",
        "max_pages": 10,
        "auth_config": {"type": "form", "username": "u", "password": "p"},
        "generate_scripts": False,
    }
    return SAPFioriCrawler(ctx, cfg)


# ---------------------------------------------------------------------------
# _normalise_url
# ---------------------------------------------------------------------------


class TestNormaliseUrl:
    def test_strips_fragment(self):
        from app.crawler.web_crawler import WebUICrawler
        assert WebUICrawler._normalise_url("https://example.com/page#section") == "https://example.com/page"

    def test_strips_trailing_hash(self):
        from app.crawler.web_crawler import WebUICrawler
        assert WebUICrawler._normalise_url("https://example.com/page#") == "https://example.com/page"

    def test_preserves_query_string(self):
        from app.crawler.web_crawler import WebUICrawler
        url = "https://example.com/search?q=hello&page=2"
        assert WebUICrawler._normalise_url(url) == url

    def test_invalid_url_returns_empty_string(self):
        from app.crawler.web_crawler import WebUICrawler
        # No scheme → treated as invalid by urlparse, returns ""
        result = WebUICrawler._normalise_url("not-a-url")
        assert result == ""

    def test_valid_url_without_fragment_unchanged(self):
        from app.crawler.web_crawler import WebUICrawler
        url = "https://example.com/path/to/page"
        assert WebUICrawler._normalise_url(url) == url


# ---------------------------------------------------------------------------
# _same_origin
# ---------------------------------------------------------------------------


class TestSameOrigin:
    def test_same_netloc(self):
        from app.crawler.web_crawler import WebUICrawler
        assert WebUICrawler._same_origin("https://example.com/a", "https://example.com/b") is True

    def test_different_host(self):
        from app.crawler.web_crawler import WebUICrawler
        assert WebUICrawler._same_origin("https://example.com/a", "https://other.com/b") is False

    def test_different_port_different_netloc(self):
        from app.crawler.web_crawler import WebUICrawler
        assert WebUICrawler._same_origin("https://example.com:443/a", "https://example.com:8443/b") is False

    def test_subdomain_is_different(self):
        from app.crawler.web_crawler import WebUICrawler
        assert WebUICrawler._same_origin("https://example.com", "https://sub.example.com") is False


# ---------------------------------------------------------------------------
# _is_excluded / _is_included
# ---------------------------------------------------------------------------


class TestPatternFilters:
    def test_excluded_pattern_blocks_url(self):
        from app.crawler.web_crawler import WebUICrawler
        assert WebUICrawler._is_excluded("https://example.com/admin/users", [r"/admin"]) is True

    def test_non_matching_exclude_passes(self):
        from app.crawler.web_crawler import WebUICrawler
        assert WebUICrawler._is_excluded("https://example.com/dashboard", [r"/logout"]) is False

    def test_no_exclude_patterns_never_excluded(self):
        from app.crawler.web_crawler import WebUICrawler
        assert WebUICrawler._is_excluded("https://example.com/anything", []) is False

    def test_included_pattern_allows_url(self):
        from app.crawler.web_crawler import WebUICrawler
        assert WebUICrawler._is_included("https://example.com/app/page", [r"/app/"]) is True

    def test_no_include_patterns_allows_nothing(self):
        # _is_included returns False when no patterns — caller should skip the check when list is empty
        from app.crawler.web_crawler import WebUICrawler
        assert WebUICrawler._is_included("https://example.com/anything", []) is False

    def test_url_not_matching_include_is_blocked(self):
        from app.crawler.web_crawler import WebUICrawler
        assert WebUICrawler._is_included("https://example.com/other/page", [r"/app/"]) is False

    def test_wildcard_glob_style_in_pattern(self):
        from app.crawler.web_crawler import WebUICrawler
        # "*" in patterns is converted to ".*" by the implementation
        assert WebUICrawler._is_excluded("https://example.com/api/v2/data", [r"/api/*"]) is True


# ---------------------------------------------------------------------------
# _classify_page_type (web heuristic)
# ---------------------------------------------------------------------------


class TestClassifyPageType:
    def _classify(self, **signals):
        from app.crawler.web_crawler import _classify_page_type
        return _classify_page_type(signals)

    def test_login_signals_detected(self):
        assert self._classify(loginForms=1, inputs=2, tables=0, charts=0, headings=1) == PageType.LOGIN

    def test_form_dominant_no_table(self):
        assert self._classify(loginForms=0, inputs=5, tables=0, charts=0, headings=2) == PageType.FORM

    def test_list_dominant(self):
        assert self._classify(loginForms=0, inputs=0, tables=2, charts=0, headings=2) == PageType.LIST

    def test_dashboard_dominant(self):
        assert self._classify(loginForms=0, inputs=0, tables=0, charts=3, headings=2) == PageType.DASHBOARD

    def test_detail_page(self):
        # Few inputs, multiple headings
        assert self._classify(loginForms=0, inputs=1, tables=0, charts=0, headings=3) == PageType.DETAIL

    def test_unknown_when_no_signals(self):
        assert self._classify(loginForms=0, inputs=0, tables=0, charts=0, headings=0) == PageType.UNKNOWN

    def test_form_requires_no_tables(self):
        # inputs >= 3 but also has a table → LIST wins
        assert self._classify(loginForms=0, inputs=4, tables=1, charts=0, headings=2) == PageType.LIST


# ---------------------------------------------------------------------------
# BaseCrawler._build_config — AuthConfig / CrawlerConfig construction
# ---------------------------------------------------------------------------


class TestBuildConfig:
    def test_default_auth_type(self):
        c = _make_web_crawler()
        assert c._crawler_config.auth_config.type == "none"

    def test_form_auth_fields_populated(self):
        c = _make_web_crawler({
            "job_id": "j", "project_id": "p", "tenant_id": "t",
            "target_url": "https://example.com",
            "launchpad_url": "",
            "max_pages": 5,
            "auth_config": {
                "type": "form",
                "username": "user@example.com",
                "password": "s3cret",
                "login_url": "https://example.com/login",
            },
            "generate_scripts": False,
        })
        auth = c._crawler_config.auth_config
        assert auth.type == "form"
        assert auth.username == "user@example.com"
        assert auth.password == "s3cret"
        assert auth.login_url == "https://example.com/login"

    def test_max_pages_propagated(self):
        c = _make_web_crawler()
        assert c._crawler_config.max_pages == 10

    def test_same_origin_default_true(self):
        c = _make_web_crawler()
        assert c._crawler_config.same_origin_only is True

    def test_bearer_token_stored(self):
        c = _make_web_crawler({
            "job_id": "j", "project_id": "p", "tenant_id": "t",
            "target_url": "https://api.example.com",
            "launchpad_url": "",
            "max_pages": 5,
            "auth_config": {"type": "bearer", "bearer_token": "tok123"},
            "generate_scripts": False,
        })
        assert c._crawler_config.auth_config.bearer_token == "tok123"

    def test_missing_auth_config_uses_defaults(self):
        c = _make_web_crawler({
            "job_id": "j", "project_id": "p", "tenant_id": "t",
            "target_url": "https://example.com",
            "launchpad_url": "",
            "max_pages": 20,
            "generate_scripts": True,
        })
        assert c._crawler_config.auth_config.type == "none"
        assert c._crawler_config.max_pages == 20


# ---------------------------------------------------------------------------
# _classify_sap_page (SAP Fiori heuristic)
# ---------------------------------------------------------------------------


class TestClassifySapPage:
    def _classify(self, **controls):
        from app.crawler.sap_fiori_crawler import _classify_sap_page
        return _classify_sap_page(controls)

    def test_form_detected(self):
        assert self._classify(hasMForm=True) == PageType.FORM

    def test_form_blocked_when_table_present(self):
        # hasMForm=True but hasMTable=True → LIST wins (table overrides form check)
        assert self._classify(hasMForm=True, hasMTable=True) == PageType.LIST

    def test_list_detected_from_m_table(self):
        assert self._classify(hasMTable=True) == PageType.LIST

    def test_list_detected_from_ui_table(self):
        assert self._classify(hasUiTable=True) == PageType.LIST

    def test_detail_detected_from_object_header(self):
        assert self._classify(hasObjectHdr=True) == PageType.DETAIL

    def test_detail_from_fcl(self):
        assert self._classify(hasFCL=True) == PageType.DETAIL

    def test_dashboard_detected(self):
        assert self._classify(hasAnalytics=True) == PageType.DASHBOARD

    def test_unknown_when_no_controls(self):
        assert self._classify() == PageType.UNKNOWN

    def test_fcl_takes_priority(self):
        # FCL (Flexible Column Layout) always → DETAIL regardless of other controls
        assert self._classify(hasFCL=True, hasMForm=True, hasAnalytics=True) == PageType.DETAIL
