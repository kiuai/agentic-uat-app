"""
Pure pytest exporter (no Selenium).

Targets API / integration tests using httpx.  Steps with type NAVIGATE or
API_CALL become HTTP requests; ASSERT steps become ``assert`` statements.

For test cases that share similar structure (same test_type == 'boundary' or
'negative'), a ``@pytest.mark.parametrize`` block is generated to group them.
"""

from __future__ import annotations

import ast
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

# ---------------------------------------------------------------------------
# Step → pytest/httpx mapping
# ---------------------------------------------------------------------------


def _step_to_py(step: TestStep, include_comments: bool) -> list[str]:
    lines: list[str] = []
    if include_comments and step.action:
        lines.append(f"    # Step {step.number}: {step.action}")

    loc = step.locator.replace("'", "\\'")
    val = step.input_value.replace("'", "\\'")
    exp = step.expected_result.replace("'", "\\'")

    if step.step_type == StepType.NAVIGATE:
        # API GET
        lines.append(f"    response = client.get('{loc}')")
        lines.append("    assert response.is_success, f\"Navigate failed: {response.status_code}\"")

    elif step.step_type == StepType.API_CALL:
        method = "post" if val else "get"
        if val:
            lines.append(f"    response = client.{method}('{loc}', json={val or '{}'})")
        else:
            lines.append(f"    response = client.{method}('{loc}')")
        lines.append("    assert response.is_success, f\"API call failed: {response.status_code}\"")

    elif step.step_type == StepType.ASSERT:
        if exp:
            lines.append(f"    assert '{exp}' in response.text, f\"Expected '{{'{exp}'}}' in response\"")
        else:
            lines.append("    assert response.is_success")

    elif step.step_type in (StepType.INPUT, StepType.CLICK):
        # For pure API tests these are logical assertions on request bodies
        lines.append(f"    # UI interaction '{step.action}' — verify via API response")
        if exp:
            lines.append(f"    assert '{exp}' in response.text")

    elif step.step_type == StepType.WAIT:
        lines.append(f"    import time; time.sleep({int(step.input_value or 1000) / 1000})")

    else:
        lines.append(f"    pass  # TODO: step {step.number} — {step.action}")

    if include_comments and step.expected_result and step.step_type != StepType.ASSERT:
        lines.append(f"    # Expected: {step.expected_result}")

    return lines


# ---------------------------------------------------------------------------
# Templates
# ---------------------------------------------------------------------------

_TEMPLATE = """\
import pytest
import httpx
{% if custom_imports %}
{% for imp in custom_imports %}
{{ imp }}
{% endfor %}
{% endif %}

BASE_URL = '{{ base_url }}'


@pytest.fixture(scope='module')
def client():
    with httpx.Client(base_url=BASE_URL, timeout=30.0) as c:
        yield c

{% for tc in standalone_cases %}

def test_{{ tc.slug }}(client):
    \"\"\"{{ tc.title }}

{% if tc.preconditions %}
    Preconditions:
{% for pre in tc.preconditions %}
    - {{ pre }}
{% endfor %}
{% endif %}
    Expected: {{ tc.expected_outcome }}
    \"\"\"
{% for line in tc.step_lines %}
{{ line }}
{% endfor %}

{% endfor %}
{% if parametrized_cases %}

@pytest.mark.parametrize('test_data', [
{% for row in parametrized_cases %}
    {{ row }},
{% endfor %}
])
def test_parametrized_{{ suite_slug }}(client, test_data):
    \"\"\"Data-driven test for {{ suite_title }}.\"\"\"
    input_val = test_data['input']
    expected  = test_data['expected']
    response  = client.post(test_data.get('endpoint', '/'), json={'value': input_val})
    assert str(expected) in response.text, (
        f"Expected {{expected!r}} for input {{input_val!r}}, got: {{response.text[:200]}}"
    )
{% endif %}
"""


# ---------------------------------------------------------------------------
# Exporter class
# ---------------------------------------------------------------------------


class PytestExporter(BaseExporter):
    """Generates pure pytest + httpx test files for API / integration testing."""

    def __init__(self, context: ExportContext | None = None) -> None:
        if context is None:
            context = ExportContext(
                project_name="KAATS",
                system_url="https://example.com",
                export_format=ExportFormat.PYTEST,
            )
        super().__init__(context)
        self._template = _jinja_env.from_string(_TEMPLATE)

    def get_file_extension(self) -> str:
        return ".py"

    def export(self, test_cases: list[TestCase] | Any) -> str:
        cases = self._coerce_input(test_cases)

        # Separate boundary/negative cases into parametrize block
        standalone: list[TestCase] = []
        data_driven: list[TestCase] = []
        for tc in cases:
            if tc.test_type in ("boundary", "negative"):
                data_driven.append(tc)
            else:
                standalone.append(tc)

        rendered_standalone = []
        for tc in standalone:
            step_lines: list[str] = []
            for step in tc.steps:
                step_lines.extend(_step_to_py(step, self.context.include_comments))
            rendered_standalone.append(
                {
                    "title": tc.title,
                    "slug": _slugify(tc.title),
                    "preconditions": tc.preconditions,
                    "step_lines": step_lines,
                    "expected_outcome": tc.expected_outcome,
                }
            )

        # Build parametrize rows for data-driven cases
        param_rows: list[str] = []
        for tc in data_driven:
            # Pull first INPUT step value + expected outcome
            input_val = ""
            for s in tc.steps:
                if s.step_type == StepType.INPUT and s.input_value:
                    input_val = s.input_value
                    break
            row = (
                f"{{'input': {input_val!r}, "
                f"'expected': {tc.expected_outcome!r}, "
                f"'label': {tc.title!r}}}"
            )
            param_rows.append(row)

        suite_title = cases[0].title if len(cases) == 1 else f"{len(cases)} Test Cases"

        return self._template.render(
            project_name=self.context.project_name,
            suite_title=suite_title,
            suite_slug=_slugify(suite_title),
            base_url=self.context.system_url,
            standalone_cases=rendered_standalone,
            parametrized_cases=param_rows,
            custom_imports=self.context.custom_imports,
        )

    def validate_output(self, content: str) -> ValidationResult:
        if not content.strip():
            return ValidationResult.fail("Output is empty.")
        try:
            ast.parse(content)
        except SyntaxError as exc:
            return ValidationResult.fail(f"Python syntax error: {exc}")
        errors: list[str] = []
        if "import pytest" not in content:
            errors.append("Missing pytest import.")
        return ValidationResult(is_valid=len(errors) == 0, errors=errors)
