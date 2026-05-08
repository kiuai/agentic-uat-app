"""
Gherkin / BDD (Cucumber-compatible) exporter.

Uses Jinja2 templates for deterministic, consistently valid Gherkin output.
"""

from __future__ import annotations

from typing import Any

from jinja2 import Template

from app.exporters.base import BaseExporter

_TEMPLATE = """Feature: {{ feature_name }}
  As a {{ actor }}
  I want to {{ goal }}
  So that {{ benefit }}

  Background:
{% for pre in preconditions %}
    Given {{ pre }}
{% endfor %}

  Scenario: {{ title }}
{% for step in steps %}
{% if step.action == 'navigate' %}
    When I navigate to "{{ step.target }}"
{% elif step.action == 'fill' %}
    And I fill in "{{ step.target }}" with "{{ step.input_data or '<value>' }}"
{% elif step.action == 'click' %}
    And I click "{{ step.target }}"
{% elif step.action == 'assert' %}
    Then I should see "{{ step.expected_result }}"
{% else %}
    And {{ step.description }}
{% endif %}
{% endfor %}
    Then {{ expected_final_state }}
"""


class GherkinExporter(BaseExporter):
    def __init__(self) -> None:
        self._template = Template(_TEMPLATE)

    def export(self, test_case: dict[str, Any]) -> str:
        actors = test_case.get("actors", ["User"])
        actor = actors[0] if actors else "User"

        return self._template.render(
            feature_name=test_case.get("title", "Feature"),
            title=test_case.get("title", "Scenario"),
            actor=actor,
            goal=test_case.get("title", "perform this action").lower(),
            benefit="the system behaves correctly",
            preconditions=test_case.get("preconditions", ["the application is running"]),
            steps=test_case.get("steps", []),
            expected_final_state=test_case.get(
                "expected_final_state", "the operation completes successfully"
            ),
        )
