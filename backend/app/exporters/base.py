"""
Abstract base exporter and shared data structures for the KAATS export engine.

All exporters follow the same contract:
  exporter = ConcreteExporter(context)
  content   = exporter.export(test_cases)         # returns str
  result    = exporter.validate_output(content)   # ValidationResult
  ext       = exporter.get_file_extension()       # e.g. ".ts"
"""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------


class StepType(str, Enum):
    NAVIGATE = "NAVIGATE"
    CLICK = "CLICK"
    INPUT = "INPUT"
    ASSERT = "ASSERT"
    WAIT = "WAIT"
    SCREENSHOT = "SCREENSHOT"
    API_CALL = "API_CALL"


class ExportFormat(str, Enum):
    PLAYWRIGHT_TS = "playwright_ts"
    PLAYWRIGHT_JS = "playwright_js"
    SELENIUM_PYTHON = "selenium_python"
    PYTEST = "pytest"
    ROBOT_FRAMEWORK = "robot_framework"
    GHERKIN = "gherkin"


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class TestStep:
    number: int
    action: str           # Human-readable description of the step
    locator: str          # CSS selector, XPath, ARIA label, or element ID
    input_value: str = "" # Data to enter (INPUT steps)
    expected_result: str = ""
    step_type: StepType = StepType.CLICK


@dataclass
class TestCase:
    id: str
    title: str
    description: str
    preconditions: list[str] = field(default_factory=list)
    steps: list[TestStep] = field(default_factory=list)
    expected_outcome: str = ""
    priority: str = "MEDIUM"
    test_type: str = "positive"  # positive | negative | boundary
    tags: list[str] = field(default_factory=list)


@dataclass
class ExportContext:
    project_name: str
    system_url: str
    export_format: ExportFormat
    include_comments: bool = True
    include_screenshots: bool = True
    custom_imports: list[str] = field(default_factory=list)
    framework_version: str = "latest"


@dataclass
class ValidationResult:
    is_valid: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @classmethod
    def ok(cls) -> "ValidationResult":
        return cls(is_valid=True)

    @classmethod
    def fail(cls, *errors: str) -> "ValidationResult":
        return cls(is_valid=False, errors=list(errors))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _slugify(text: str) -> str:
    """Convert a title to a valid Python/Robot identifier."""
    slug = re.sub(r"[^\w\s]", "", text.lower())
    return re.sub(r"\s+", "_", slug).strip("_") or "test"


def _escape_single_quote(value: str) -> str:
    return value.replace("'", "\\'")


def _escape_double_quote(value: str) -> str:
    return value.replace('"', '\\"')


# ---------------------------------------------------------------------------
# Abstract base
# ---------------------------------------------------------------------------


class BaseExporter(ABC):
    """
    Abstract base for all KAATS format exporters.

    Subclasses must implement:
      - export(test_cases)  → str
      - get_file_extension() → str (including leading dot)

    The base provides a default validate_output() that subclasses should
    override with format-specific checks.
    """

    def __init__(self, context: ExportContext) -> None:
        self.context = context

    @abstractmethod
    def export(self, test_cases: list[TestCase]) -> str:
        """Return the complete script content as a string."""

    @abstractmethod
    def get_file_extension(self) -> str:
        """Return file extension including the dot, e.g. '.ts', '.py', '.robot'."""

    def validate_output(self, content: str) -> ValidationResult:
        """
        Syntax-validate the generated output.

        The default implementation just checks the output is non-empty.
        Subclasses override with format-specific validation.
        """
        if not content or not content.strip():
            return ValidationResult.fail("Generated output is empty.")
        return ValidationResult.ok()

    # ── Shared helpers ────────────────────────────────────────────────────────

    @staticmethod
    def _slugify(text: str) -> str:
        return _slugify(text)

    @staticmethod
    def _escape_sq(value: str) -> str:
        return _escape_single_quote(value)

    @staticmethod
    def _escape_dq(value: str) -> str:
        return _escape_double_quote(value)

    # ── Backward-compat shim —————————————————————————————————————————————————
    # Old code called exporter.export(test_case_dict).  New code calls with
    # a list[TestCase].  Accept both at the method boundary.

    def _coerce_input(self, arg: Any) -> list[TestCase]:
        """Accept dict, list[dict], or list[TestCase] and normalise to list[TestCase]."""
        if isinstance(arg, TestCase):
            return [arg]
        if isinstance(arg, dict):
            return [self._dict_to_test_case(arg)]
        if isinstance(arg, list):
            out: list[TestCase] = []
            for item in arg:
                if isinstance(item, TestCase):
                    out.append(item)
                elif isinstance(item, dict):
                    out.append(self._dict_to_test_case(item))
            return out
        return []

    @staticmethod
    def _dict_to_test_case(d: dict[str, Any]) -> TestCase:
        """Convert a legacy dict (from Cosmos doc) to a typed TestCase."""
        raw_steps = d.get("steps", [])
        steps: list[TestStep] = []
        for i, s in enumerate(raw_steps, start=1):
            if isinstance(s, TestStep):
                steps.append(s)
                continue
            step_type_raw = s.get("step_type", s.get("action", "CLICK")).upper()
            try:
                step_type = StepType(step_type_raw)
            except ValueError:
                # Legacy action names like 'navigate', 'fill', 'click'
                _legacy = {
                    "NAVIGATE": StepType.NAVIGATE,
                    "FILL": StepType.INPUT,
                    "SELECT": StepType.INPUT,
                    "CLICK": StepType.CLICK,
                    "ASSERT": StepType.ASSERT,
                    "WAIT": StepType.WAIT,
                    "SCREENSHOT": StepType.SCREENSHOT,
                    "API_CALL": StepType.API_CALL,
                }
                step_type = _legacy.get(step_type_raw, StepType.CLICK)

            steps.append(
                TestStep(
                    number=s.get("step_number", s.get("number", i)),
                    action=s.get("description", s.get("action", "")),
                    locator=s.get("target", s.get("locator", "")),
                    input_value=s.get("input_data", s.get("input_value", s.get("value", ""))),
                    expected_result=s.get("expected_result", ""),
                    step_type=step_type,
                )
            )

        return TestCase(
            id=d.get("id", ""),
            title=d.get("title", "Untitled Test"),
            description=d.get("description", ""),
            preconditions=d.get("preconditions", []),
            steps=steps,
            expected_outcome=d.get("expected_outcome", d.get("expected_final_state", "")),
            priority=d.get("priority", "MEDIUM"),
            test_type=d.get("test_type", "positive"),
            tags=d.get("tags", []),
        )
