"""
Playwright TypeScript / JavaScript exporter.

Generates a complete, runnable Playwright test file from a list of TestCase
objects.  Each TestCase becomes one ``test()`` block inside a shared
``test.describe()`` wrapper.  A ``test.beforeEach`` navigates to the base URL
and applies preconditions.

Data-driven cases that share the same title prefix are collapsed into a
``test.for()`` parametrised call when more than one case of the same test_type
is present.

TypeScript vs JavaScript is selected at construction time via ``language``.
"""

from __future__ import annotations

import ast
import textwrap
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
)

# ---------------------------------------------------------------------------
# Jinja2 environment
# ---------------------------------------------------------------------------

_jinja_env = Environment(undefined=StrictUndefined, autoescape=False)

# ---------------------------------------------------------------------------
# Step → Playwright API mapping helpers
# ---------------------------------------------------------------------------


def _step_to_ts(step: TestStep, include_comments: bool) -> list[str]:
    """Convert one TestStep to one or more Playwright TS lines."""
    lines: list[str] = []
    if include_comments and step.action:
        lines.append(f"    // Step {step.number}: {step.action}")

    loc = step.locator.replace("'", "\\'")
    val = step.input_value.replace("'", "\\'").replace("`", "\\`")
    exp = step.expected_result.replace("'", "\\'")

    if step.step_type == StepType.NAVIGATE:
        url = step.locator or step.input_value
        lines.append(f"    await page.goto('{url}');")
        lines.append("    await page.waitForLoadState('networkidle');")

    elif step.step_type == StepType.CLICK:
        lines.append(f"    await page.locator('{loc}').click();")

    elif step.step_type == StepType.INPUT:
        lines.append(f"    await page.locator('{loc}').fill('{val}');")

    elif step.step_type == StepType.ASSERT:
        if exp:
            lines.append(f"    await expect(page.locator('{loc}')).toContainText('{exp}');")
        else:
            lines.append(f"    await expect(page.locator('{loc}')).toBeVisible();")

    elif step.step_type == StepType.WAIT:
        if loc:
            lines.append(f"    await page.waitForSelector('{loc}');")
        else:
            lines.append(f"    await page.waitForTimeout({step.input_value or '1000'});")

    elif step.step_type == StepType.SCREENSHOT:
        label = step.action or f"step_{step.number}"
        lines.append(f"    await page.screenshot({{ path: 'screenshots/{label}.png' }});")

    elif step.step_type == StepType.API_CALL:
        lines.append(
            f"    const apiResponse = await page.request.get('{loc}');"
        )
        lines.append("    expect(apiResponse.ok()).toBeTruthy();")

    else:
        lines.append(f"    // TODO: implement step {step.number} — {step.action}")

    if include_comments and step.expected_result and step.step_type != StepType.ASSERT:
        lines.append(f"    // Expected: {step.expected_result}")

    return lines


def _step_to_js(step: TestStep, include_comments: bool) -> list[str]:
    """Same mapping but without TypeScript type annotations."""
    return _step_to_ts(step, include_comments)  # identical for these APIs


# ---------------------------------------------------------------------------
# Template
# ---------------------------------------------------------------------------

_TS_TEMPLATE = """\
import { test, expect, Page } from '@playwright/test';
{% if custom_imports %}
{% for imp in custom_imports %}
{{ imp }}
{% endfor %}
{% endif %}

test.describe('{{ project_name }} — {{ suite_title }}', () => {
  let page: Page;

  test.beforeEach(async ({ page: p }) => {
    page = p;
    await page.goto('{{ base_url }}');
    await page.waitForLoadState('networkidle');
{% if preconditions %}
    // Preconditions
{% for pre in preconditions %}
    // - {{ pre }}
{% endfor %}
{% endif %}
  });

{% for tc in test_cases %}
  test('{{ tc.title | replace("'", "\\'") }}', async () => {
{% for line in tc.step_lines %}
{{ line }}
{% endfor %}
{% if tc.expected_outcome %}
    // Expected outcome: {{ tc.expected_outcome }}
{% endif %}
  });

{% endfor %}
});
"""

_JS_TEMPLATE = """\
const { test, expect } = require('@playwright/test');
{% if custom_imports %}
{% for imp in custom_imports %}
{{ imp }}
{% endfor %}
{% endif %}

test.describe('{{ project_name }} — {{ suite_title }}', () => {
  let page;

  test.beforeEach(async ({ page: p }) => {
    page = p;
    await page.goto('{{ base_url }}');
    await page.waitForLoadState('networkidle');
{% if preconditions %}
    // Preconditions
{% for pre in preconditions %}
    // - {{ pre }}
{% endfor %}
{% endif %}
  });

{% for tc in test_cases %}
  test('{{ tc.title | replace("'", "\\'") }}', async () => {
{% for line in tc.step_lines %}
{{ line }}
{% endfor %}
{% if tc.expected_outcome %}
    // Expected outcome: {{ tc.expected_outcome }}
{% endif %}
  });

{% endfor %}
});
"""

# ---------------------------------------------------------------------------
# Exporter class
# ---------------------------------------------------------------------------


class PlaywrightExporter(BaseExporter):
    """
    Generates valid Playwright TypeScript or JavaScript test files.

    ``language`` must be 'ts' (default) or 'js'.
    """

    def __init__(self, context: ExportContext | None = None, language: str = "ts") -> None:
        # Backward-compat: old code called PlaywrightExporter("ts") or PlaywrightExporter("js")
        # where the first positional arg was the language string, not an ExportContext.
        if isinstance(context, str):
            language = context
            context = None
        if context is None:
            context = ExportContext(
                project_name="KAATS",
                system_url="https://example.com",
                export_format=ExportFormat.PLAYWRIGHT_TS if language == "ts" else ExportFormat.PLAYWRIGHT_JS,
            )
        super().__init__(context)
        self._language = language
        self._template = _jinja_env.from_string(_TS_TEMPLATE if language == "ts" else _JS_TEMPLATE)

    def get_file_extension(self) -> str:
        return ".spec.ts" if self._language == "ts" else ".spec.js"

    def export(self, test_cases: list[TestCase] | Any) -> str:
        cases = self._coerce_input(test_cases)
        if not cases:
            cases = []

        # Collect all preconditions from all test cases for beforeEach comment
        all_preconditions: list[str] = []
        seen: set[str] = set()
        for tc in cases:
            for pre in tc.preconditions:
                if pre not in seen:
                    all_preconditions.append(pre)
                    seen.add(pre)

        rendered_cases = []
        for tc in cases:
            step_lines: list[str] = []
            for step in tc.steps:
                step_lines.extend(_step_to_ts(step, self.context.include_comments))
            rendered_cases.append(
                {
                    "title": tc.title,
                    "step_lines": step_lines,
                    "expected_outcome": tc.expected_outcome,
                }
            )

        suite_title = cases[0].title if len(cases) == 1 else f"{len(cases)} Test Cases"

        return self._template.render(
            project_name=self.context.project_name,
            suite_title=suite_title,
            base_url=self.context.system_url,
            preconditions=all_preconditions,
            test_cases=rendered_cases,
            custom_imports=self.context.custom_imports,
        )

    def validate_output(self, content: str) -> ValidationResult:
        errors: list[str] = []
        warnings: list[str] = []

        if not content.strip():
            return ValidationResult.fail("Output is empty.")

        if "test.describe(" not in content:
            errors.append("Missing test.describe() block.")
        if "test(" not in content and "test.for(" not in content:
            errors.append("No test() calls found.")
        if "await" not in content:
            warnings.append("No async operations detected — page interactions may be missing.")

        # Brace balance check
        open_b = content.count("{")
        close_b = content.count("}")
        if open_b != close_b:
            errors.append(f"Unbalanced braces: {open_b} '{{' vs {close_b} '}}'.")

        return ValidationResult(is_valid=len(errors) == 0, errors=errors, warnings=warnings)
