"""
LangChain LCEL chains for the test generation pipeline.

Architecture
------------
Each chain is a pure async function that:
1. Formats the appropriate prompt
2. Calls AzureOpenAIClient (with tenacity retry inside the client)
3. Parses and validates the JSON response
4. Returns typed Pydantic objects + a UsageRecord

Caching
-------
Identical requirement inputs are cached for 1 hour using an in-memory TTL
dict. In production, swap _cache_get/_cache_set to use Azure Cache for Redis
by setting REDIS_URL in config and replacing the implementation below.

Usage tracking
--------------
Every AI call records (tenant_id, company_id, tokens, cost_usd) for billing
visibility. Call sites must pass context.company_id.
"""

from __future__ import annotations

import ast
import hashlib
import json
import re
import subprocess
import time
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

import structlog

from app.ai.client import AzureOpenAIClient, UsageRecord, get_ai_client
from app.ai.prompts.crawler_analysis import (
    CRAWL_FLOW_TO_TEST_CASES_PROMPT,
    CRAWL_PAGE_TO_REQUIREMENTS_PROMPT,
)
from app.ai.prompts.requirement_analysis import (
    REQUIREMENT_CLASSIFICATION_PROMPT,
    REQUIREMENT_QUALITY_CHECK_PROMPT,
)
from app.ai.prompts.test_generation import (
    REQUIREMENT_TO_TEST_CASES_PROMPT,
    TEST_CASES_TO_GHERKIN_PROMPT,
    TEST_CASES_TO_PLAYWRIGHT_PROMPT,
    TEST_CASES_TO_PYTEST_PROMPT,
    TEST_CASES_TO_ROBOT_FRAMEWORK_PROMPT,
    TEST_CASES_TO_SELENIUM_PROMPT,
)
from app.models.test_script import ScriptFormat

logger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Typed data classes
# ---------------------------------------------------------------------------


@dataclass
class GenerationContext:
    """Project-level context passed to every chain call."""

    company_id: UUID
    project_id: UUID
    base_url: str = "https://example.com"
    system_type: str = "WEB"
    company_name: str = "KAATS"
    industry: str = "Software"
    feature_name: str = "Application"
    include_assertions: bool = True
    include_negative_cases: bool = False
    max_steps_per_script: int = 20


@dataclass
class TestStep:
    step_number: int
    action: str
    expected_result: str
    input_data: str | None = None


@dataclass
class TestCase:
    test_case_id: str
    title: str
    description: str
    preconditions: list[str]
    test_steps: list[TestStep]
    expected_outcome: str
    priority: str
    test_type: str


@dataclass
class GeneratedScript:
    format: ScriptFormat
    content: str
    test_case_count: int
    usage: UsageRecord


@dataclass
class QualityCheckResult:
    quality_score: int
    improvement_suggestions: list[str]
    missing_information: list[str]
    testability_verdict: str
    recommended_test_count: int
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass
class RequirementClassification:
    requirement_type: str
    priority: str
    business_domain: str
    functional_areas: list[str]
    suggested_test_types: list[str]
    compliance_tags: list[str]
    estimated_complexity: str
    raw: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# In-memory TTL cache (swap to Redis for multi-replica production)
# ---------------------------------------------------------------------------

_CACHE_TTL = 3600  # 1 hour
_cache: dict[str, tuple[Any, float]] = {}


def _cache_key(*parts: str) -> str:
    payload = "|".join(parts)
    return hashlib.sha256(payload.encode()).hexdigest()


def _cache_get(key: str) -> Any | None:
    entry = _cache.get(key)
    if entry is None:
        return None
    value, ts = entry
    if time.monotonic() - ts > _CACHE_TTL:
        del _cache[key]
        return None
    return value


def _cache_set(key: str, value: Any) -> None:
    _cache[key] = (value, time.monotonic())


# ---------------------------------------------------------------------------
# Content safety filter
# ---------------------------------------------------------------------------

_CREDENTIAL_PATTERNS = [
    re.compile(r'(?i)(password|passwd|pwd|secret|api[_-]?key)\s*[=:]\s*["\']?[^\s"\']{4,}'),
    re.compile(r'(?i)bearer\s+[a-zA-Z0-9._-]{20,}'),
    re.compile(r'(?i)sk-[a-zA-Z0-9]{20,}'),  # OpenAI-style keys
]
_LOCALHOST_PATTERN = re.compile(r'(?i)(localhost|127\.0\.0\.[0-9]+|::1)')
_PII_PATTERNS = [
    re.compile(r'\b\d{3}[-.]?\d{2}[-.]?\d{4}\b'),  # SSN
    re.compile(r'\b[A-Z]{2}\d{6,9}\b'),             # Passport number pattern
]


def _check_content_safety(content: str) -> list[str]:
    """Return a list of safety violation descriptions (empty = safe)."""
    violations: list[str] = []
    for pat in _CREDENTIAL_PATTERNS:
        if pat.search(content):
            violations.append("Potential hardcoded credential detected.")
            break
    if _LOCALHOST_PATTERN.search(content):
        violations.append("Localhost URL detected in generated script.")
    for pat in _PII_PATTERNS:
        if pat.search(content):
            violations.append("Potential PII pattern detected.")
            break
    return violations


# ---------------------------------------------------------------------------
# Script syntax validation
# ---------------------------------------------------------------------------


def _validate_python_syntax(code: str) -> list[str]:
    """Return errors (empty = valid)."""
    try:
        ast.parse(code)
        return []
    except SyntaxError as exc:
        return [f"Python syntax error at line {exc.lineno}: {exc.msg}"]


def _validate_ts_syntax(code: str) -> list[str]:
    """
    Validate TypeScript/JavaScript by running `node --check` on a temp file.
    Falls back gracefully if Node.js is not available.
    """
    import tempfile
    import os

    try:
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".mjs", delete=False
        ) as f:
            # Strip TS-specific syntax for basic node check
            js_code = re.sub(r":\s*\w+(\[\])?", "", code)
            js_code = re.sub(r"<[^>]+>", "", js_code)
            f.write(js_code)
            tmp_path = f.name

        result = subprocess.run(
            ["node", "--check", tmp_path],
            capture_output=True,
            text=True,
            timeout=10,
        )
        os.unlink(tmp_path)

        if result.returncode != 0:
            return [f"JS syntax error: {result.stderr[:500]}"]
        return []
    except FileNotFoundError:
        # Node.js not installed — skip validation
        return []
    except subprocess.TimeoutExpired:
        return ["Syntax validation timed out."]
    except Exception:
        return []


def validate_script(content: str, fmt: ScriptFormat) -> list[str]:
    """Return list of validation errors; empty = OK to save."""
    errors: list[str] = []

    # Safety first
    safety_issues = _check_content_safety(content)
    errors.extend(safety_issues)

    # Syntax check
    python_formats = {
        ScriptFormat.SELENIUM_PYTHON,
        ScriptFormat.PYTEST,
        ScriptFormat.ROBOT_FRAMEWORK,
    }
    ts_formats = {
        ScriptFormat.PLAYWRIGHT_TS,
        ScriptFormat.PLAYWRIGHT_JS,
    }

    if fmt in python_formats:
        if fmt != ScriptFormat.ROBOT_FRAMEWORK:
            errors.extend(_validate_python_syntax(content))
    elif fmt in ts_formats:
        errors.extend(_validate_ts_syntax(content))
    # Gherkin: no syntax validator available, skip

    return errors


# ---------------------------------------------------------------------------
# Chain functions
# ---------------------------------------------------------------------------


def _prompt_to_messages(prompt_template, variables: dict[str, Any]) -> list[dict[str, str]]:
    """Render a LangChain ChatPromptTemplate to OpenAI messages format."""
    rendered = prompt_template.format_messages(**variables)
    return [{"role": m.type if m.type != "human" else "user", "content": m.content}
            for m in rendered]


async def check_requirement_quality(
    requirement_title: str,
    requirement_content: str,
    *,
    context: GenerationContext,
    client: AzureOpenAIClient | None = None,
) -> tuple[QualityCheckResult, UsageRecord]:
    """Stage 0: Quality gate before test generation."""
    if client is None:
        client = get_ai_client()

    cache_key = _cache_key("quality", requirement_title, requirement_content[:200])
    cached = _cache_get(cache_key)
    if cached:
        logger.debug("quality_check_cache_hit", title=requirement_title)
        return cached

    messages = _prompt_to_messages(
        REQUIREMENT_QUALITY_CHECK_PROMPT,
        {
            "requirement_title": requirement_title,
            "requirement_content": requirement_content,
        },
    )
    data, usage = await client.complete_json(
        messages, temperature=0.1, company_id=str(context.company_id)
    )

    result = QualityCheckResult(
        quality_score=data.get("quality_score", 50),
        improvement_suggestions=data.get("improvement_suggestions", []),
        missing_information=data.get("missing_information", []),
        testability_verdict=data.get("testability_verdict", "POOR"),
        recommended_test_count=data.get("recommended_test_count", 3),
        raw=data,
    )
    _cache_set(cache_key, (result, usage))
    logger.info(
        "requirement_quality_checked",
        title=requirement_title,
        score=result.quality_score,
        verdict=result.testability_verdict,
    )
    return result, usage


async def classify_requirement(
    requirement_title: str,
    requirement_content: str,
    *,
    context: GenerationContext,
    client: AzureOpenAIClient | None = None,
) -> tuple[RequirementClassification, UsageRecord]:
    """Classify a requirement for domain, type, and recommended test coverage."""
    if client is None:
        client = get_ai_client()

    cache_key = _cache_key("classify", requirement_title, requirement_content[:200])
    cached = _cache_get(cache_key)
    if cached:
        return cached

    messages = _prompt_to_messages(
        REQUIREMENT_CLASSIFICATION_PROMPT,
        {
            "requirement_title": requirement_title,
            "requirement_content": requirement_content,
        },
    )
    data, usage = await client.complete_json(
        messages, temperature=0.1, company_id=str(context.company_id)
    )

    result = RequirementClassification(
        requirement_type=data.get("requirement_type", "functional"),
        priority=data.get("priority", "MEDIUM"),
        business_domain=data.get("business_domain", "GENERAL"),
        functional_areas=data.get("functional_areas", []),
        suggested_test_types=data.get("suggested_test_types", ["positive"]),
        compliance_tags=data.get("compliance_tags", []),
        estimated_complexity=data.get("estimated_complexity", "MEDIUM"),
        raw=data,
    )
    _cache_set(cache_key, (result, usage))
    return result, usage


async def generate_test_cases_from_requirement(
    requirement_title: str,
    requirement_content: str,
    *,
    context: GenerationContext,
    business_domain: str = "GENERAL",
    priority: str = "MEDIUM",
    client: AzureOpenAIClient | None = None,
) -> tuple[list[TestCase], UsageRecord]:
    """
    Stage 1: Requirement text → list of structured TestCase objects.

    Caches on (requirement_title, first-200-chars-of-content).
    """
    if client is None:
        client = get_ai_client()

    cache_key = _cache_key(
        "test_cases",
        requirement_title,
        requirement_content[:200],
        context.system_type,
    )
    cached = _cache_get(cache_key)
    if cached:
        logger.debug("test_cases_cache_hit", title=requirement_title)
        return cached

    messages = _prompt_to_messages(
        REQUIREMENT_TO_TEST_CASES_PROMPT,
        {
            "requirement_title": requirement_title,
            "requirement_content": requirement_content,
            "business_domain": business_domain,
            "priority": priority,
            "industry": context.industry,
            "system_type": context.system_type,
        },
    )

    data, usage = await client.complete_json(
        messages,
        temperature=0.2,
        max_tokens=4096,
        company_id=str(context.company_id),
    )

    raw_cases: list[dict[str, Any]] = data.get("test_cases", [])
    test_cases: list[TestCase] = []
    for tc in raw_cases:
        steps = [
            TestStep(
                step_number=s.get("step_number", i + 1),
                action=s.get("action", ""),
                expected_result=s.get("expected_result", ""),
                input_data=s.get("input_data"),
            )
            for i, s in enumerate(tc.get("test_steps", []))
        ]
        test_cases.append(
            TestCase(
                test_case_id=tc.get("test_case_id", f"TC-{len(test_cases)+1:03d}"),
                title=tc.get("title", ""),
                description=tc.get("description", ""),
                preconditions=tc.get("preconditions", []),
                test_steps=steps,
                expected_outcome=tc.get("expected_outcome", ""),
                priority=tc.get("priority", "MEDIUM"),
                test_type=tc.get("test_type", "positive"),
            )
        )

    logger.info(
        "test_cases_generated",
        requirement=requirement_title,
        count=len(test_cases),
        tokens=usage.total_tokens,
    )
    result = (test_cases, usage)
    _cache_set(cache_key, result)
    return result


async def generate_script_from_test_cases(
    test_cases: list[TestCase],
    export_format: ScriptFormat,
    *,
    context: GenerationContext,
    client: AzureOpenAIClient | None = None,
) -> GeneratedScript:
    """
    Stage 2: TestCase list → formatted script string.

    Chooses the right prompt template based on export_format.
    Validates the generated script before returning.
    """
    if client is None:
        client = get_ai_client()

    prompt_map = {
        ScriptFormat.PLAYWRIGHT_TS: TEST_CASES_TO_PLAYWRIGHT_PROMPT,
        ScriptFormat.PLAYWRIGHT_JS: TEST_CASES_TO_PLAYWRIGHT_PROMPT,
        ScriptFormat.SELENIUM_PYTHON: TEST_CASES_TO_SELENIUM_PROMPT,
        ScriptFormat.PYTEST: TEST_CASES_TO_PYTEST_PROMPT,
        ScriptFormat.ROBOT_FRAMEWORK: TEST_CASES_TO_ROBOT_FRAMEWORK_PROMPT,
        ScriptFormat.GHERKIN: TEST_CASES_TO_GHERKIN_PROMPT,
    }
    prompt = prompt_map.get(export_format, TEST_CASES_TO_PLAYWRIGHT_PROMPT)

    # Serialize test cases for the prompt
    cases_dict = [
        {
            "test_case_id": tc.test_case_id,
            "title": tc.title,
            "description": tc.description,
            "preconditions": tc.preconditions,
            "test_steps": [
                {
                    "step_number": s.step_number,
                    "action": s.action,
                    "expected_result": s.expected_result,
                    "input_data": s.input_data,
                }
                for s in tc.test_steps
            ],
            "expected_outcome": tc.expected_outcome,
            "priority": tc.priority,
            "test_type": tc.test_type,
        }
        for tc in test_cases
    ]

    messages = _prompt_to_messages(
        prompt,
        {
            "base_url": context.base_url,
            "feature_name": context.feature_name,
            "test_cases_json": json.dumps(cases_dict, indent=2),
            # Extra vars for some prompts
            "application_name": context.company_name,
            "flow_name": context.feature_name,
        },
    )

    content, usage = await client.complete(
        messages,
        temperature=0.0,
        max_tokens=8192,
        company_id=str(context.company_id),
    )
    content = str(content).strip()

    # Strip any markdown code fences the model may have added anyway
    content = re.sub(r"^```[a-z]*\n?", "", content, flags=re.MULTILINE)
    content = re.sub(r"\n?```$", "", content, flags=re.MULTILINE)
    content = content.strip()

    # Validate
    errors = validate_script(content, export_format)
    if errors:
        logger.warning(
            "script_validation_failed",
            format=export_format.value,
            errors=errors,
        )
        # Surface the issues but don't hard-fail — service layer decides
        raise ValueError(
            f"Generated script failed validation ({export_format.value}): "
            + "; ".join(errors)
        )

    logger.info(
        "script_generated",
        format=export_format.value,
        test_case_count=len(test_cases),
        tokens=usage.total_tokens,
    )

    return GeneratedScript(
        format=export_format,
        content=content,
        test_case_count=len(test_cases),
        usage=usage,
    )


async def analyze_crawl_page(
    page_url: str,
    page_title: str,
    elements_json: str,
    outbound_links_json: str,
    *,
    context: GenerationContext,
    client: AzureOpenAIClient | None = None,
) -> tuple[list[dict[str, Any]], UsageRecord]:
    """Single crawled page → list of inferred requirement dicts."""
    if client is None:
        client = get_ai_client()

    cache_key = _cache_key("crawl_page", page_url, elements_json[:300])
    cached = _cache_get(cache_key)
    if cached:
        return cached

    messages = _prompt_to_messages(
        CRAWL_PAGE_TO_REQUIREMENTS_PROMPT,
        {
            "page_url": page_url,
            "page_title": page_title or page_url,
            "elements_json": elements_json,
            "outbound_links_json": outbound_links_json,
        },
    )
    data, usage = await client.complete_json(
        messages, temperature=0.2, company_id=str(context.company_id)
    )
    requirements: list[dict[str, Any]] = data.get("requirements", [])
    result = (requirements, usage)
    _cache_set(cache_key, result)
    return result


async def analyze_crawl_flow(
    flow_name: str,
    flow_pages: list[dict[str, Any]],
    elements_summary: str,
    *,
    context: GenerationContext,
    client: AzureOpenAIClient | None = None,
) -> tuple[list[TestCase], UsageRecord]:
    """Page flow → TestCase list covering happy path + error paths."""
    if client is None:
        client = get_ai_client()

    messages = _prompt_to_messages(
        CRAWL_FLOW_TO_TEST_CASES_PROMPT,
        {
            "application_name": context.company_name,
            "flow_name": flow_name,
            "flow_pages_json": json.dumps(flow_pages, indent=2),
            "elements_summary": elements_summary,
        },
    )
    data, usage = await client.complete_json(
        messages, temperature=0.2, company_id=str(context.company_id)
    )

    raw_cases: list[dict[str, Any]] = data.get("test_cases", [])
    test_cases: list[TestCase] = []
    for tc in raw_cases:
        steps = [
            TestStep(
                step_number=s.get("step_number", i + 1),
                action=s.get("action", ""),
                expected_result=s.get("expected_result", ""),
                input_data=s.get("input_data"),
            )
            for i, s in enumerate(tc.get("test_steps", []))
        ]
        test_cases.append(
            TestCase(
                test_case_id=tc.get("test_case_id", f"TC-{len(test_cases)+1:03d}"),
                title=tc.get("title", ""),
                description=tc.get("description", ""),
                preconditions=tc.get("preconditions", []),
                test_steps=steps,
                expected_outcome=tc.get("expected_outcome", ""),
                priority=tc.get("priority", "MEDIUM"),
                test_type=tc.get("test_type", "positive"),
            )
        )
    return test_cases, usage


# ---------------------------------------------------------------------------
# Backward-compat wrappers (used by old worker code)
# ---------------------------------------------------------------------------


async def run_decompose(
    requirement_content: str,
    company_name: str = "KAATS",
    industry: str = "Software",
) -> list[dict[str, Any]]:
    """Legacy wrapper — calls generate_test_cases_from_requirement."""
    ctx = GenerationContext(
        company_id=UUID("00000000-0000-0000-0000-000000000000"),
        project_id=UUID("00000000-0000-0000-0000-000000000000"),
        company_name=company_name,
        industry=industry,
    )
    cases, _ = await generate_test_cases_from_requirement(
        "Requirement", requirement_content, context=ctx
    )
    return [
        {
            "scenario_id": tc.test_case_id,
            "title": tc.title,
            "preconditions": tc.preconditions,
            "test_type": tc.test_type,
            "priority": tc.priority,
        }
        for tc in cases
    ]


async def run_generate_steps(
    scenario: dict[str, Any],
    app_description: str = "Web application",
) -> dict[str, Any]:
    """Legacy wrapper — returns scenario as-is (steps already generated)."""
    return scenario


async def run_format_playwright_ts(
    test_case: dict[str, Any],
    base_url: str = "https://example.com",
) -> str:
    """Legacy wrapper — generates Playwright TS from a single test case dict."""
    steps = [
        TestStep(
            step_number=s.get("step_number", i + 1),
            action=s.get("action", ""),
            expected_result=s.get("expected_result", ""),
        )
        for i, s in enumerate(test_case.get("steps", []))
    ]
    tc = TestCase(
        test_case_id=test_case.get("scenario_id", "TC-001"),
        title=test_case.get("title", ""),
        description="",
        preconditions=[],
        test_steps=steps,
        expected_outcome=test_case.get("expected_final_state", ""),
        priority="MEDIUM",
        test_type="positive",
    )
    ctx = GenerationContext(
        company_id=UUID("00000000-0000-0000-0000-000000000000"),
        project_id=UUID("00000000-0000-0000-0000-000000000000"),
        base_url=base_url,
    )
    script = await generate_script_from_test_cases(
        [tc], ScriptFormat.PLAYWRIGHT_TS, context=ctx
    )
    return script.content
