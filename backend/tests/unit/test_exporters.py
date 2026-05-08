"""Unit tests for test script exporters."""

from __future__ import annotations

import pytest

from app.exporters.gherkin_exporter import GherkinExporter
from app.exporters.playwright_exporter import PlaywrightExporter
from app.exporters.pytest_exporter import PytestExporter
from app.exporters.robot_framework_exporter import RobotFrameworkExporter
from app.exporters.selenium_exporter import SeleniumExporter

SAMPLE_TEST_CASE = {
    "title": "Login with valid credentials",
    "preconditions": ["User account exists", "Application is running"],
    "actors": ["End User"],
    "steps": [
        {
            "step_number": 1,
            "action": "navigate",
            "description": "Navigate to login page",
            "target": "/login",
            "input_data": None,
            "expected_result": "Login page displayed",
        },
        {
            "step_number": 2,
            "action": "fill",
            "description": "Enter email",
            "target": "Email",
            "input_data": "user@example.com",
            "expected_result": None,
        },
        {
            "step_number": 3,
            "action": "click",
            "description": "Click Sign In",
            "target": "Sign In",
            "input_data": None,
            "expected_result": "User is redirected to dashboard",
        },
    ],
    "expected_final_state": "User is authenticated and on dashboard",
}


def test_playwright_ts_export_contains_test_structure() -> None:
    exporter = PlaywrightExporter("ts")
    output = exporter.export(SAMPLE_TEST_CASE)
    assert "import { test, expect }" in output
    assert "test.describe" in output
    assert "Login with valid credentials" in output


def test_playwright_js_export() -> None:
    exporter = PlaywrightExporter("js")
    output = exporter.export(SAMPLE_TEST_CASE)
    assert "require('@playwright/test')" in output


def test_selenium_export_contains_unittest() -> None:
    exporter = SeleniumExporter()
    output = exporter.export(SAMPLE_TEST_CASE)
    assert "import unittest" in output
    assert "webdriver.Chrome()" in output


def test_pytest_export_contains_page_fixture() -> None:
    exporter = PytestExporter()
    output = exporter.export(SAMPLE_TEST_CASE)
    assert "def test_" in output
    assert "page: Page" in output


def test_robot_framework_export_has_settings_section() -> None:
    exporter = RobotFrameworkExporter()
    output = exporter.export(SAMPLE_TEST_CASE)
    assert "*** Settings ***" in output
    assert "*** Test Cases ***" in output


def test_gherkin_export_has_feature_and_scenario() -> None:
    exporter = GherkinExporter()
    output = exporter.export(SAMPLE_TEST_CASE)
    assert "Feature:" in output
    assert "Scenario:" in output
    assert "Given" in output
    assert "When" in output
