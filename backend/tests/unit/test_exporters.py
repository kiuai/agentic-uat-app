"""
Unit tests for the KAATS export engine.

Coverage:
- base.py: _dict_to_test_case, _slugify, ValidationResult helpers
- PlaywrightExporter: TS / JS output structure and validation
- SeleniumExporter: Python syntax, class naming, fixture presence
- PytestExporter: Python syntax, parametrize for boundary cases
- RobotFrameworkExporter: all required .robot sections
- GherkinExporter: Feature / Scenario / step keywords
- StepType dispatch: each step type renders correct API call
- Backward-compat: legacy dict input still works
"""

from __future__ import annotations

import ast

import pytest

from app.exporters.base import (
    ExportContext,
    ExportFormat,
    StepType,
    TestCase,
    TestStep,
    ValidationResult,
    _slugify,
)
from app.exporters.gherkin_exporter import GherkinExporter
from app.exporters.playwright_exporter import PlaywrightExporter
from app.exporters.pytest_exporter import PytestExporter
from app.exporters.robot_framework_exporter import RobotFrameworkExporter
from app.exporters.selenium_exporter import SeleniumExporter


# ---------------------------------------------------------------------------
# Fixtures and shared helpers
# ---------------------------------------------------------------------------


def _ctx(fmt: ExportFormat = ExportFormat.PLAYWRIGHT_TS) -> ExportContext:
    return ExportContext(
        project_name="Acme Corp",
        system_url="https://app.example.com",
        export_format=fmt,
    )


def _login_case() -> TestCase:
    return TestCase(
        id="tc-001",
        title="User Login",
        description="Verify a valid user can log in",
        preconditions=["The application is running", "User account exists"],
        steps=[
            TestStep(1, "Navigate to login page", "https://app.example.com/login",
                     step_type=StepType.NAVIGATE),
            TestStep(2, "Enter username", "#username", "admin@example.com",
                     step_type=StepType.INPUT),
            TestStep(3, "Enter password", "#password", "secret123",
                     step_type=StepType.INPUT),
            TestStep(4, "Click login button", "button[type=submit]",
                     step_type=StepType.CLICK),
            TestStep(5, "Assert dashboard visible", ".dashboard-header", "Welcome",
                     step_type=StepType.ASSERT),
        ],
        expected_outcome="User is redirected to dashboard",
        priority="CRITICAL",
        test_type="positive",
    )


def _api_case() -> TestCase:
    return TestCase(
        id="tc-002",
        title="Create User API",
        description="POST /users creates a new user",
        steps=[
            TestStep(1, "Send POST request", "/api/users", '{"name": "Test"}',
                     step_type=StepType.API_CALL),
            TestStep(2, "Assert 201 status", "", "201", step_type=StepType.ASSERT),
        ],
        expected_outcome="User created successfully",
        test_type="positive",
    )


def _boundary_cases() -> list[TestCase]:
    data = [("", "required"), ("a" * 256, "too long"), ("  ", "invalid")]
    return [
        TestCase(
            id=f"tc-b0{i}",
            title=f"Boundary Input {i}",
            description="Boundary test",
            steps=[
                TestStep(1, "Enter value", "#input", val, step_type=StepType.INPUT),
                TestStep(2, "Assert result", "#result", expected, step_type=StepType.ASSERT),
            ],
            expected_outcome=expected,
            test_type="boundary",
        )
        for i, (val, expected) in enumerate(data)
    ]


# ---------------------------------------------------------------------------
# base.py helpers
# ---------------------------------------------------------------------------


class TestBaseHelpers:
    def test_slugify_basic(self):
        assert _slugify("User Login Test") == "user_login_test"

    def test_slugify_special_chars(self):
        # Non-word chars stripped, spaces → underscore
        result = _slugify("Test: Create & Verify!")
        assert " " not in result
        assert "test" in result

    def test_slugify_empty_returns_test(self):
        assert _slugify("") == "test"

    def test_slugify_only_special_chars(self):
        assert _slugify("!!!") == "test"

    def test_validation_result_ok(self):
        r = ValidationResult.ok()
        assert r.is_valid is True
        assert r.errors == []

    def test_validation_result_fail_collects_errors(self):
        r = ValidationResult.fail("error one", "error two")
        assert r.is_valid is False
        assert "error one" in r.errors
        assert "error two" in r.errors

    def test_dict_to_test_case_navigate_action(self):
        """Legacy dict with action='navigate' maps to StepType.NAVIGATE."""
        from app.exporters.base import BaseExporter

        class _E(BaseExporter):
            def export(self, _): return ""
            def get_file_extension(self): return ""

        e = _E(_ctx())
        d = {
            "id": "x", "title": "Nav Test", "description": "",
            "steps": [
                {"step_number": 1, "action": "navigate", "target": "https://example.com",
                 "description": "go home"},
            ],
        }
        tc = e._dict_to_test_case(d)
        assert tc.steps[0].step_type == StepType.NAVIGATE

    def test_dict_to_test_case_input_step(self):
        from app.exporters.base import BaseExporter

        class _E(BaseExporter):
            def export(self, _): return ""
            def get_file_extension(self): return ""

        e = _E(_ctx())
        d = {
            "id": "x", "title": "T", "description": "",
            "steps": [
                {"number": 1, "step_type": "INPUT", "action": "fill form",
                 "locator": "#email", "input_value": "a@b.com", "expected_result": ""},
            ],
        }
        tc = e._dict_to_test_case(d)
        assert tc.steps[0].step_type == StepType.INPUT
        assert tc.steps[0].input_value == "a@b.com"

    def test_dict_to_test_case_fill_action_maps_to_input(self):
        from app.exporters.base import BaseExporter

        class _E(BaseExporter):
            def export(self, _): return ""
            def get_file_extension(self): return ""

        e = _E(_ctx())
        d = {
            "id": "x", "title": "T", "description": "",
            "steps": [{"step_number": 1, "action": "fill", "target": "#name",
                        "input_data": "hello", "description": "enter name"}],
        }
        tc = e._dict_to_test_case(d)
        assert tc.steps[0].step_type == StepType.INPUT


# ---------------------------------------------------------------------------
# PlaywrightExporter
# ---------------------------------------------------------------------------


class TestPlaywrightExporter:
    def test_ts_contains_playwright_import(self):
        e = PlaywrightExporter(_ctx(ExportFormat.PLAYWRIGHT_TS), language="ts")
        out = e.export([_login_case()])
        assert "from '@playwright/test'" in out

    def test_ts_contains_test_describe(self):
        e = PlaywrightExporter(_ctx(), language="ts")
        out = e.export([_login_case()])
        assert "test.describe(" in out

    def test_ts_contains_before_each(self):
        e = PlaywrightExporter(_ctx(), language="ts")
        out = e.export([_login_case()])
        assert "test.beforeEach" in out

    def test_ts_navigate_renders_goto(self):
        e = PlaywrightExporter(_ctx(), language="ts")
        out = e.export([_login_case()])
        assert "page.goto(" in out

    def test_ts_input_renders_fill(self):
        e = PlaywrightExporter(_ctx(), language="ts")
        out = e.export([_login_case()])
        assert ".fill(" in out

    def test_ts_click_renders_click(self):
        e = PlaywrightExporter(_ctx(), language="ts")
        out = e.export([_login_case()])
        assert ".click()" in out

    def test_ts_assert_renders_expect(self):
        e = PlaywrightExporter(_ctx(), language="ts")
        out = e.export([_login_case()])
        assert "expect(" in out

    def test_js_uses_require(self):
        e = PlaywrightExporter(_ctx(ExportFormat.PLAYWRIGHT_JS), language="js")
        out = e.export([_login_case()])
        assert "require('@playwright/test')" in out

    def test_js_extension(self):
        e = PlaywrightExporter(_ctx(ExportFormat.PLAYWRIGHT_JS), language="js")
        assert e.get_file_extension() == ".spec.js"

    def test_ts_extension(self):
        e = PlaywrightExporter(_ctx(), language="ts")
        assert e.get_file_extension() == ".spec.ts"

    def test_multiple_cases_all_titles_present(self):
        e = PlaywrightExporter(_ctx(), language="ts")
        out = e.export([_login_case(), _api_case()])
        assert "User Login" in out
        assert "Create User API" in out

    def test_legacy_dict_input(self):
        """Backward-compat: pass a dict and it still renders."""
        e = PlaywrightExporter(_ctx(), language="ts")
        d = {
            "title": "Login with valid credentials",
            "preconditions": ["App running"],
            "steps": [
                {"step_number": 1, "action": "navigate", "target": "/login",
                 "description": "go to login"},
            ],
        }
        out = e.export(d)
        assert "test.describe(" in out

    def test_validation_valid_output(self):
        e = PlaywrightExporter(_ctx(), language="ts")
        out = e.export([_login_case()])
        assert e.validate_output(out).is_valid

    def test_validation_empty_fails(self):
        e = PlaywrightExporter(_ctx(), language="ts")
        assert not e.validate_output("").is_valid

    def test_validation_missing_test_block_fails(self):
        e = PlaywrightExporter(_ctx(), language="ts")
        assert not e.validate_output("import { test } from '@playwright/test';").is_valid


# ---------------------------------------------------------------------------
# SeleniumExporter
# ---------------------------------------------------------------------------


class TestSeleniumExporter:
    def test_output_is_valid_python(self):
        e = SeleniumExporter(_ctx(ExportFormat.SELENIUM_PYTHON))
        ast.parse(e.export([_login_case()]))

    def test_has_pytest_fixture(self):
        e = SeleniumExporter(_ctx(ExportFormat.SELENIUM_PYTHON))
        assert "@pytest.fixture" in e.export([_login_case()])

    def test_has_driver_quit(self):
        e = SeleniumExporter(_ctx(ExportFormat.SELENIUM_PYTHON))
        assert "drv.quit()" in e.export([_login_case()])

    def test_navigate_renders_driver_get(self):
        e = SeleniumExporter(_ctx(ExportFormat.SELENIUM_PYTHON))
        assert "driver.get(" in e.export([_login_case()])

    def test_click_uses_webdriver_wait(self):
        e = SeleniumExporter(_ctx(ExportFormat.SELENIUM_PYTHON))
        assert "WebDriverWait" in e.export([_login_case()])

    def test_input_renders_send_keys(self):
        e = SeleniumExporter(_ctx(ExportFormat.SELENIUM_PYTHON))
        assert "send_keys(" in e.export([_login_case()])

    def test_assert_contains_assert_keyword(self):
        e = SeleniumExporter(_ctx(ExportFormat.SELENIUM_PYTHON))
        out = e.export([_login_case()])
        assert "assert " in out

    def test_extension(self):
        e = SeleniumExporter(_ctx(ExportFormat.SELENIUM_PYTHON))
        assert e.get_file_extension() == ".py"

    def test_validation_valid(self):
        e = SeleniumExporter(_ctx(ExportFormat.SELENIUM_PYTHON))
        assert e.validate_output(e.export([_login_case()])).is_valid


# ---------------------------------------------------------------------------
# PytestExporter
# ---------------------------------------------------------------------------


class TestPytestExporter:
    def test_output_is_valid_python(self):
        e = PytestExporter(_ctx(ExportFormat.PYTEST))
        ast.parse(e.export([_api_case()]))

    def test_has_import_pytest(self):
        e = PytestExporter(_ctx(ExportFormat.PYTEST))
        assert "import pytest" in e.export([_api_case()])

    def test_has_httpx_client(self):
        e = PytestExporter(_ctx(ExportFormat.PYTEST))
        assert "httpx" in e.export([_api_case()])

    def test_boundary_cases_generate_parametrize(self):
        e = PytestExporter(_ctx(ExportFormat.PYTEST))
        assert "@pytest.mark.parametrize" in e.export(_boundary_cases())

    def test_positive_case_generates_standalone_function(self):
        e = PytestExporter(_ctx(ExportFormat.PYTEST))
        assert "def test_" in e.export([_api_case()])

    def test_extension(self):
        e = PytestExporter(_ctx(ExportFormat.PYTEST))
        assert e.get_file_extension() == ".py"

    def test_validation_valid(self):
        e = PytestExporter(_ctx(ExportFormat.PYTEST))
        assert e.validate_output(e.export([_api_case()])).is_valid


# ---------------------------------------------------------------------------
# RobotFrameworkExporter
# ---------------------------------------------------------------------------


class TestRobotFrameworkExporter:
    def test_has_settings_section(self):
        e = RobotFrameworkExporter(_ctx(ExportFormat.ROBOT_FRAMEWORK))
        assert "*** Settings ***" in e.export([_login_case()])

    def test_has_variables_section(self):
        e = RobotFrameworkExporter(_ctx(ExportFormat.ROBOT_FRAMEWORK))
        assert "*** Variables ***" in e.export([_login_case()])

    def test_has_test_cases_section(self):
        e = RobotFrameworkExporter(_ctx(ExportFormat.ROBOT_FRAMEWORK))
        assert "*** Test Cases ***" in e.export([_login_case()])

    def test_has_keywords_section(self):
        e = RobotFrameworkExporter(_ctx(ExportFormat.ROBOT_FRAMEWORK))
        assert "*** Keywords ***" in e.export([_login_case()])

    def test_has_selenium_library(self):
        e = RobotFrameworkExporter(_ctx(ExportFormat.ROBOT_FRAMEWORK))
        assert "SeleniumLibrary" in e.export([_login_case()])

    def test_navigate_renders_go_to(self):
        e = RobotFrameworkExporter(_ctx(ExportFormat.ROBOT_FRAMEWORK))
        assert "Go To" in e.export([_login_case()])

    def test_click_renders_click_element(self):
        e = RobotFrameworkExporter(_ctx(ExportFormat.ROBOT_FRAMEWORK))
        assert "Click Element" in e.export([_login_case()])

    def test_input_renders_input_text(self):
        e = RobotFrameworkExporter(_ctx(ExportFormat.ROBOT_FRAMEWORK))
        assert "Input Text" in e.export([_login_case()])

    def test_assert_renders_wait_until_page_contains(self):
        e = RobotFrameworkExporter(_ctx(ExportFormat.ROBOT_FRAMEWORK))
        out = e.export([_login_case()])
        assert "Wait Until Page Contains" in out or "Element Should Be Visible" in out

    def test_extension(self):
        e = RobotFrameworkExporter(_ctx(ExportFormat.ROBOT_FRAMEWORK))
        assert e.get_file_extension() == ".robot"

    def test_validation_all_sections_present(self):
        e = RobotFrameworkExporter(_ctx(ExportFormat.ROBOT_FRAMEWORK))
        assert e.validate_output(e.export([_login_case()])).is_valid


# ---------------------------------------------------------------------------
# GherkinExporter
# ---------------------------------------------------------------------------


class TestGherkinExporter:
    def test_has_feature(self):
        e = GherkinExporter(_ctx(ExportFormat.GHERKIN))
        assert "Feature:" in e.export([_login_case()])

    def test_has_scenario(self):
        e = GherkinExporter(_ctx(ExportFormat.GHERKIN))
        assert "Scenario:" in e.export([_login_case()])

    def test_navigate_becomes_when_or_given(self):
        e = GherkinExporter(_ctx(ExportFormat.GHERKIN))
        out = e.export([_login_case()])
        assert "I navigate to" in out

    def test_input_becomes_enter_step(self):
        e = GherkinExporter(_ctx(ExportFormat.GHERKIN))
        out = e.export([_login_case()])
        assert 'I enter "' in out

    def test_assert_becomes_then_should_see(self):
        e = GherkinExporter(_ctx(ExportFormat.GHERKIN))
        out = e.export([_login_case()])
        assert "Then I should see" in out

    def test_boundary_cases_generate_scenario_outline(self):
        e = GherkinExporter(_ctx(ExportFormat.GHERKIN))
        out = e.export(_boundary_cases())
        assert "Scenario Outline:" in out
        assert "Examples:" in out

    def test_shared_preconditions_go_in_background(self):
        case1 = TestCase("c1", "T1", "", preconditions=["App running", "User exists"],
                         steps=[TestStep(1, "click", "#btn", step_type=StepType.CLICK)],
                         test_type="positive")
        case2 = TestCase("c2", "T2", "", preconditions=["App running"],
                         steps=[TestStep(1, "click", "#btn2", step_type=StepType.CLICK)],
                         test_type="positive")
        e = GherkinExporter(_ctx(ExportFormat.GHERKIN))
        out = e.export([case1, case2])
        assert "Background:" in out
        assert "App running" in out

    def test_extension(self):
        e = GherkinExporter(_ctx(ExportFormat.GHERKIN))
        assert e.get_file_extension() == ".feature"

    def test_validation_valid(self):
        e = GherkinExporter(_ctx(ExportFormat.GHERKIN))
        assert e.validate_output(e.export([_login_case()])).is_valid

    def test_validation_empty_fails(self):
        e = GherkinExporter(_ctx(ExportFormat.GHERKIN))
        assert not e.validate_output("").is_valid
