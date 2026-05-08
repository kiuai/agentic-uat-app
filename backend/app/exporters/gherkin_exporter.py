"""
Gherkin / BDD exporter (Cucumber / SpecFlow / Behave compatible).

Generates ``.feature`` files with:
  - Feature header with role/goal/benefit narrative
  - Background section from shared preconditions
  - One Scenario per positive TestCase
  - Scenario Outline + Examples table for boundary/negative test cases that
    share the same step structure but different input values

Step keywords follow the Given/When/Then/And convention:
  NAVIGATE    → When I navigate to "..."
  CLICK       → When I click on "..."
  INPUT       → When I enter "..." in the "..." field
  ASSERT      → Then I should see "..."
  WAIT        → When I wait for "..."
  API_CALL    → When I send a GET/POST request to "..."
"""

from __future__ import annotations

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

_INDENT = "    "


# ---------------------------------------------------------------------------
# Step → Gherkin step text
# ---------------------------------------------------------------------------


def _step_to_gherkin(step: TestStep, index: int) -> str:
    """Return a single Gherkin step line (no keyword prefix — caller adds it)."""
    loc = step.locator
    val = step.input_value
    exp = step.expected_result

    if step.step_type == StepType.NAVIGATE:
        url = loc or val
        return f'I navigate to "{url}"'

    elif step.step_type == StepType.CLICK:
        label = loc or step.action or "the element"
        return f'I click on "{label}"'

    elif step.step_type == StepType.INPUT:
        field = loc or "the field"
        return f'I enter "{val}" in the "{field}" field'

    elif step.step_type == StepType.ASSERT:
        text = exp or loc or "the expected result"
        return f'I should see "{text}"'

    elif step.step_type == StepType.WAIT:
        target = loc or f"{val or 1000}ms"
        return f'I wait for "{target}"'

    elif step.step_type == StepType.SCREENSHOT:
        return f'I take a screenshot of "{step.action or "the page"}"'

    elif step.step_type == StepType.API_CALL:
        return f'I send a request to "{loc}"'

    else:
        return step.action or f"I perform step {step.number}"


def _steps_to_gherkin_lines(steps: list[TestStep]) -> list[str]:
    """Convert a list of TestStep objects into Gherkin step lines with keywords."""
    lines: list[str] = []
    expect_keyword_used = False

    for i, step in enumerate(steps):
        text = _step_to_gherkin(step, i)

        if step.step_type == StepType.ASSERT:
            keyword = "Then" if not expect_keyword_used else "And"
            expect_keyword_used = True
        elif i == 0:
            keyword = "Given" if step.step_type == StepType.NAVIGATE else "When"
        else:
            keyword = "And"

        lines.append(f"{_INDENT}{_INDENT}{keyword} {text}")

    return lines


# ---------------------------------------------------------------------------
# Outline builder
# ---------------------------------------------------------------------------


def _build_outline_steps(cases: list[TestCase]) -> tuple[list[str], list[dict[str, str]]]:
    """
    For data-driven cases sharing the same step count, build a Scenario Outline.

    Returns (outline_steps, examples_rows) where each row is {column: value}.
    """
    if not cases:
        return [], []

    # Use first case as template; replace input_value with placeholder <input>
    template_case = cases[0]
    outline_steps: list[str] = []
    has_input = False

    for i, step in enumerate(template_case.steps):
        text = _step_to_gherkin(step, i)
        if step.step_type == StepType.INPUT and step.input_value:
            # Replace the value with a placeholder
            text = text.replace(f'"{step.input_value}"', '"<input>"')
            has_input = True
        if step.step_type == StepType.ASSERT and step.expected_result:
            text = text.replace(f'"{step.expected_result}"', '"<expected>"')

        if i == 0:
            keyword = "Given" if step.step_type == StepType.NAVIGATE else "When"
        elif step.step_type == StepType.ASSERT:
            keyword = "Then"
        else:
            keyword = "And"
        outline_steps.append(f"{_INDENT}{_INDENT}{keyword} {text}")

    if not has_input:
        return [], []

    # Build examples table
    examples: list[dict[str, str]] = []
    for tc in cases:
        row: dict[str, str] = {}
        for step in tc.steps:
            if step.step_type == StepType.INPUT and step.input_value:
                row["input"] = step.input_value
            if step.step_type == StepType.ASSERT and step.expected_result:
                row["expected"] = step.expected_result
        row.setdefault("input", "")
        row.setdefault("expected", tc.expected_outcome or "success")
        examples.append(row)

    return outline_steps, examples


# ---------------------------------------------------------------------------
# Template
# ---------------------------------------------------------------------------

_TEMPLATE = """\
Feature: {{ feature_title }}
{{ _INDENT }}As a {{ actor }}
{{ _INDENT }}I want to {{ goal }}
{{ _INDENT }}So that {{ benefit }}

{% if background_steps %}
{{ _INDENT }}Background:
{% for step in background_steps %}
{{ step }}
{% endfor %}

{% endif %}
{% for scenario in scenarios %}
{{ _INDENT }}Scenario: {{ scenario.title }}
{% if scenario.description %}
{{ _INDENT }}{{ _INDENT }}[{{ scenario.description }}]
{% endif %}
{% for line in scenario.steps %}
{{ line }}
{% endfor %}

{% endfor %}
{% if outlines %}
{% for outline in outlines %}
{{ _INDENT }}Scenario Outline: {{ outline.title }}
{% for line in outline.steps %}
{{ line }}
{% endfor %}

{{ _INDENT }}{{ _INDENT }}Examples:
{{ _INDENT }}{{ _INDENT }}  | input | expected |
{% for row in outline.examples %}
{{ _INDENT }}{{ _INDENT }}  | {{ row.input | ljust(20) }} | {{ row.expected | ljust(20) }} |
{% endfor %}

{% endfor %}
{% endif %}
"""


# ---------------------------------------------------------------------------
# Exporter class
# ---------------------------------------------------------------------------


class GherkinExporter(BaseExporter):
    """Generates Cucumber/SpecFlow-compatible Gherkin .feature files."""

    def __init__(self, context: ExportContext | None = None) -> None:
        if context is None:
            context = ExportContext(
                project_name="KAATS",
                system_url="https://example.com",
                export_format=ExportFormat.GHERKIN,
            )
        super().__init__(context)
        self._template = _jinja_env.from_string(_TEMPLATE)

    def get_file_extension(self) -> str:
        return ".feature"

    def export(self, test_cases: list[TestCase] | Any) -> str:
        cases = self._coerce_input(test_cases)

        # ── Feature narrative ─────────────────────────────────────────────
        first = cases[0] if cases else None
        feature_title = self.context.project_name
        actor = "user"
        goal = first.description or first.title if first else "use the system"
        benefit = "the system behaves as expected"

        # ── Background: shared preconditions ──────────────────────────────
        shared_preconditions: list[str] = []
        if cases:
            common = set(cases[0].preconditions)
            for tc in cases[1:]:
                common &= set(tc.preconditions)
            shared_preconditions = [f"{_INDENT}{_INDENT}Given {pre}" for pre in sorted(common)]

        # ── Scenarios ────────────────────────────────────────────────────
        positive_cases = [tc for tc in cases if tc.test_type == "positive"]
        data_driven_cases = [tc for tc in cases if tc.test_type in ("boundary", "negative")]

        scenarios = []
        for tc in positive_cases:
            step_lines = _steps_to_gherkin_lines(tc.steps)
            # Add unique preconditions (those not in Background)
            extra_pres = [
                p for p in tc.preconditions if p not in shared_preconditions
            ]
            preamble = [f"{_INDENT}{_INDENT}Given {p}" for p in extra_pres]
            scenarios.append(
                {
                    "title": tc.title,
                    "description": tc.description,
                    "steps": preamble + step_lines,
                }
            )

        # Also render non-positive cases that didn't go into outline
        for tc in data_driven_cases:
            step_lines = _steps_to_gherkin_lines(tc.steps)
            scenarios.append(
                {
                    "title": f"{tc.title} ({tc.test_type})",
                    "description": tc.description,
                    "steps": step_lines,
                }
            )

        # ── Scenario Outlines ─────────────────────────────────────────────
        outlines = []
        if len(data_driven_cases) > 1:
            outline_steps, examples = _build_outline_steps(data_driven_cases)
            if outline_steps and examples:
                outlines.append(
                    {
                        "title": f"{feature_title} — Data-Driven",
                        "steps": outline_steps,
                        "examples": examples,
                    }
                )
                # Remove those from plain scenario list
                for tc in data_driven_cases:
                    scenarios = [s for s in scenarios if s["title"] not in (tc.title, f"{tc.title} ({tc.test_type})")]

        return self._template.render(
            feature_title=feature_title,
            actor=actor,
            goal=goal.lower().rstrip("."),
            benefit=benefit,
            background_steps=shared_preconditions,
            scenarios=scenarios,
            outlines=outlines,
            _INDENT=_INDENT,
        )

    def validate_output(self, content: str) -> ValidationResult:
        errors: list[str] = []
        if "Feature:" not in content:
            errors.append("Missing 'Feature:' declaration.")
        if "Scenario:" not in content and "Scenario Outline:" not in content:
            errors.append("No Scenario or Scenario Outline blocks found.")
        if "When" not in content and "Then" not in content:
            errors.append("No Given/When/Then steps found.")
        return ValidationResult(is_valid=len(errors) == 0, errors=errors)
