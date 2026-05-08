"""Pytest exporter."""

from __future__ import annotations

from typing import Any

from jinja2 import Template

from app.exporters.base import BaseExporter

_TEMPLATE = """import pytest
from playwright.sync_api import Page, expect


def test_{{ title | lower | replace(' ', '_') }}(page: Page):
    \"\"\"{{ title }}
    Preconditions: {{ preconditions | join('; ') }}
    \"\"\"
{% for step in steps %}
    # Step {{ step.step_number }}: {{ step.description }}
{% if step.action == 'navigate' %}
    page.goto('{{ step.target }}')
    page.wait_for_load_state('networkidle')
{% elif step.action == 'fill' %}
    page.get_by_label('{{ step.target }}').fill('{{ step.input_data or '' }}')
{% elif step.action == 'click' %}
    page.get_by_role('button', name='{{ step.target }}').click()
{% endif %}
{% if step.expected_result %}
    # Expected: {{ step.expected_result }}
{% endif %}
{% endfor %}
"""


class PytestExporter(BaseExporter):
    def __init__(self) -> None:
        self._template = Template(_TEMPLATE)

    def export(self, test_case: dict[str, Any]) -> str:
        return self._template.render(
            title=test_case.get("title", "Test"),
            preconditions=test_case.get("preconditions", []),
            steps=test_case.get("steps", []),
        )
