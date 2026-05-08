"""
Robot Framework exporter.

Generates ``.robot`` files using SeleniumLibrary keywords.  Common step
sequences are extracted into reusable ``*** Keywords ***`` blocks to keep the
test cases readable.

Output sections:
  *** Settings ***      — Library imports, Suite Setup/Teardown
  *** Variables ***     — BASE_URL, configurable flags
  *** Test Cases ***    — One case per TestCase, using keyword calls
  *** Keywords ***      — Open/Close browser + reusable step keywords
"""

from __future__ import annotations

import re
from typing import Any

from jinja2 import Environment, StrictUndefined

from app.exporters.base import (
    BaseExporter,
    ExportContext,
    ExportFormat,
    StepType,
    TestCase,
    TestStep,
    ValidationResult,
    _slugify,
)

_jinja_env = Environment(undefined=StrictUndefined, autoescape=False)

# Robot Framework requires 4-space (or 2-space) indentation and at least 2
# spaces between keyword and arguments.
_SEP = "    "  # 4-space canonical indent / arg separator


# ---------------------------------------------------------------------------
# Step → Robot Framework keyword call
# ---------------------------------------------------------------------------


def _step_to_rf(step: TestStep, include_comments: bool) -> list[str]:
    lines: list[str] = []
    if include_comments and step.action:
        lines.append(f"{_SEP}# Step {step.number}: {step.action}")

    loc = step.locator
    val = step.input_value
    exp = step.expected_result

    if step.step_type == StepType.NAVIGATE:
        url = loc or val
        lines.append(f"{_SEP}Go To{_SEP}{url}")
        lines.append(f"{_SEP}Wait Until Page Contains Element{_SEP}css:body{_SEP}30s")

    elif step.step_type == StepType.CLICK:
        lines.append(f"{_SEP}Wait Until Element Is Enabled{_SEP}css:{loc}{_SEP}10s")
        lines.append(f"{_SEP}Click Element{_SEP}css:{loc}")

    elif step.step_type == StepType.INPUT:
        lines.append(f"{_SEP}Wait Until Element Is Visible{_SEP}css:{loc}{_SEP}10s")
        lines.append(f"{_SEP}Input Text{_SEP}css:{loc}{_SEP}{val}")

    elif step.step_type == StepType.ASSERT:
        if exp:
            lines.append(f"{_SEP}Wait Until Page Contains{_SEP}{exp}{_SEP}10s")
        else:
            lines.append(f"{_SEP}Element Should Be Visible{_SEP}css:{loc}")

    elif step.step_type == StepType.WAIT:
        if loc:
            lines.append(f"{_SEP}Wait Until Element Is Visible{_SEP}css:{loc}{_SEP}10s")
        else:
            secs = float(val or 1000) / 1000
            lines.append(f"{_SEP}Sleep{_SEP}{secs:.1f}s")

    elif step.step_type == StepType.SCREENSHOT:
        label = _slugify(step.action or f"step_{step.number}")
        lines.append(f"{_SEP}Capture Page Screenshot{_SEP}{label}.png")

    elif step.step_type == StepType.API_CALL:
        lines.append(f"{_SEP}${{{_slugify(step.action or 'response')}}}=    GET    {loc}")
        lines.append(f"{_SEP}Should Be True    ${{status_code}} < 400")

    else:
        lines.append(f"{_SEP}Log    TODO: step {step.number} — {step.action}    WARN")

    if include_comments and step.expected_result and step.step_type != StepType.ASSERT:
        lines.append(f"{_SEP}# Expected: {step.expected_result}")

    return lines


# ---------------------------------------------------------------------------
# Template
# ---------------------------------------------------------------------------

_TEMPLATE = """\
*** Settings ***
Library           SeleniumLibrary
Library           Collections
Library           String
{% for lib in custom_libraries %}
Library           {{ lib }}
{% endfor %}
Suite Setup       Open Test Browser
Suite Teardown    Close All Browsers

*** Variables ***
${BASE_URL}       {{ base_url }}
${BROWSER}        chrome
${HEADLESS}       True
${TIMEOUT}        10s

*** Test Cases ***
{% for tc in test_cases %}
{{ tc.title }}
    [Documentation]    {{ tc.description or tc.title }}
    [Tags]    {{ tc.tags | join('    ') }}
{% if tc.preconditions %}
    # Preconditions
{% for pre in tc.preconditions %}
    Log    Precondition: {{ pre }}
{% endfor %}
{% endif %}
{% for line in tc.step_lines %}
{{ line }}
{% endfor %}

{% endfor %}
*** Keywords ***
Open Test Browser
    [Documentation]    Open browser and navigate to base URL
    ${options}=    Evaluate    sys.modules['selenium.webdriver'].ChromeOptions()    sys
    Run Keyword If    ${HEADLESS}    Call Method    ${options}    add_argument    --headless=new
    Call Method    ${options}    add_argument    --no-sandbox
    Call Method    ${options}    add_argument    --window-size=1920,1080
    Create Webdriver    Chrome    options=${options}
    Set Window Size    1920    1080
    Go To    ${BASE_URL}
    Maximize Browser Window

Wait And Click
    [Arguments]    ${locator}
    [Documentation]    Wait for element to be clickable and click it
    Wait Until Element Is Enabled    ${locator}    timeout=${TIMEOUT}
    Click Element    ${locator}

Wait And Input
    [Arguments]    ${locator}    ${value}
    [Documentation]    Wait for element and enter text
    Wait Until Element Is Visible    ${locator}    timeout=${TIMEOUT}
    Clear Element Text    ${locator}
    Input Text    ${locator}    ${value}

Assert Text Present
    [Arguments]    ${expected_text}
    [Documentation]    Assert the page contains the given text
    Wait Until Page Contains    ${expected_text}    timeout=${TIMEOUT}

Assert Element Visible
    [Arguments]    ${locator}
    [Documentation]    Assert element is visible on the page
    Wait Until Element Is Visible    ${locator}    timeout=${TIMEOUT}
    Element Should Be Visible    ${locator}
"""


# ---------------------------------------------------------------------------
# Exporter class
# ---------------------------------------------------------------------------


class RobotFrameworkExporter(BaseExporter):
    """Generates Robot Framework .robot files using SeleniumLibrary."""

    def __init__(self, context: ExportContext | None = None) -> None:
        if context is None:
            context = ExportContext(
                project_name="KAATS",
                system_url="https://example.com",
                export_format=ExportFormat.ROBOT_FRAMEWORK,
            )
        super().__init__(context)
        self._template = _jinja_env.from_string(_TEMPLATE)

    def get_file_extension(self) -> str:
        return ".robot"

    def export(self, test_cases: list[TestCase] | Any) -> str:
        cases = self._coerce_input(test_cases)

        rendered_cases = []
        for tc in cases:
            step_lines: list[str] = []
            for step in tc.steps:
                step_lines.extend(_step_to_rf(step, self.context.include_comments))

            tags = list(tc.tags) or ["automated", "kaats-generated"]
            if tc.priority:
                tags.append(tc.priority.lower())
            if tc.test_type:
                tags.append(tc.test_type)

            rendered_cases.append(
                {
                    "title": tc.title,
                    "description": tc.description,
                    "preconditions": tc.preconditions,
                    "step_lines": step_lines,
                    "tags": tags,
                }
            )

        # Extract custom library names from custom_imports
        custom_libs = [
            imp.replace("Library", "").strip()
            for imp in self.context.custom_imports
            if "Library" in imp
        ]

        return self._template.render(
            project_name=self.context.project_name,
            base_url=self.context.system_url,
            test_cases=rendered_cases,
            custom_libraries=custom_libs,
        )

    def validate_output(self, content: str) -> ValidationResult:
        errors: list[str] = []
        required_sections = [
            "*** Settings ***",
            "*** Variables ***",
            "*** Test Cases ***",
            "*** Keywords ***",
        ]
        for section in required_sections:
            if section not in content:
                errors.append(f"Missing required section: {section}")

        if "SeleniumLibrary" not in content:
            errors.append("Missing SeleniumLibrary import.")

        return ValidationResult(is_valid=len(errors) == 0, errors=errors)
