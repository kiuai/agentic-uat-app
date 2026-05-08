"""Playwright TypeScript/JavaScript exporter."""

from __future__ import annotations

import json
from typing import Any

from jinja2 import Template

from app.exporters.base import BaseExporter

_TS_TEMPLATE = """import { test, expect } from '@playwright/test';

test.describe('{{ title }}', () => {
  test('{{ title }}', async ({ page }) => {
    // Preconditions: {{ preconditions | join(', ') }}
{% for step in steps %}
    // Step {{ step.step_number }}: {{ step.description }}
{% if step.action == 'navigate' %}
    await page.goto('{{ step.target }}');
    await page.waitForLoadState('networkidle');
{% elif step.action == 'fill' %}
    await page.getByLabel('{{ step.target }}').fill('{{ step.input_data or '' }}');
{% elif step.action == 'click' %}
    await page.getByRole('button', { name: '{{ step.target }}' }).click();
{% elif step.action == 'select' %}
    await page.getByLabel('{{ step.target }}').selectOption('{{ step.input_data or '' }}');
{% endif %}
{% if step.expected_result %}
    // Expected: {{ step.expected_result }}
{% endif %}
{% endfor %}
  });
});
"""

_JS_TEMPLATE = """const { test, expect } = require('@playwright/test');

test.describe('{{ title }}', () => {
  test('{{ title }}', async ({ page }) => {
{% for step in steps %}
    // Step {{ step.step_number }}: {{ step.description }}
{% if step.action == 'navigate' %}
    await page.goto('{{ step.target }}');
    await page.waitForLoadState('networkidle');
{% elif step.action == 'fill' %}
    await page.getByLabel('{{ step.target }}').fill('{{ step.input_data or '' }}');
{% elif step.action == 'click' %}
    await page.getByRole('button', { name: '{{ step.target }}' }).click();
{% endif %}
{% endfor %}
  });
});
"""


class PlaywrightExporter(BaseExporter):
    def __init__(self, language: str = "ts") -> None:
        self._template = Template(_TS_TEMPLATE if language == "ts" else _JS_TEMPLATE)

    def export(self, test_case: dict[str, Any]) -> str:
        return self._template.render(
            title=test_case.get("title", "Test"),
            preconditions=test_case.get("preconditions", []),
            steps=test_case.get("steps", []),
        )
