"""Robot Framework exporter."""

from __future__ import annotations

from typing import Any

from jinja2 import Template

from app.exporters.base import BaseExporter

_TEMPLATE = """*** Settings ***
Library    Browser    auto_closing_level=SUITE
Suite Setup    New Browser    headless=${HEADLESS}
Suite Teardown    Close Browser

*** Variables ***
${HEADLESS}    true
${BASE_URL}    ${ENV_BASE_URL}

*** Test Cases ***
{{ title }}
    [Documentation]    {{ title }}
    ...    Preconditions: {{ preconditions | join('; ') }}
    [Tags]    automated    kaats-generated
{% for step in steps %}
    # Step {{ step.step_number }}: {{ step.description }}
{% if step.action == 'navigate' %}
    New Page    ${BASE_URL}{{ step.target }}
    Wait For Load State    networkidle
{% elif step.action == 'fill' %}
    Fill Text    label={{ step.target }}    {{ step.input_data or '' }}
{% elif step.action == 'click' %}
    Click    "{{ step.target }}"
{% endif %}
{% endfor %}

*** Keywords ***
Setup Test Session
    [Documentation]    Common setup for all tests
    Set Browser Timeout    30s
"""


class RobotFrameworkExporter(BaseExporter):
    def __init__(self) -> None:
        self._template = Template(_TEMPLATE)

    def export(self, test_case: dict[str, Any]) -> str:
        return self._template.render(
            title=test_case.get("title", "Test"),
            preconditions=test_case.get("preconditions", []),
            steps=test_case.get("steps", []),
        )
