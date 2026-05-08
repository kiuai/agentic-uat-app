"""Unit tests for AI generation chains.

Tests cover:
- Content safety filtering
- Python/TS syntax validation
- Script validation orchestration
- In-memory TTL cache
- Prompt-to-messages rendering
- Chain functions (LLM calls mocked via AsyncMock)
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID

import pytest

import app.ai.chains as _chains_module
from app.ai.chains import (
    GenerationContext,
    GeneratedScript,
    QualityCheckResult,
    RequirementClassification,
    TestCase,
    TestStep,
    _CACHE_TTL,
    _cache_get,
    _cache_key,
    _cache_set,
    _check_content_safety,
    _prompt_to_messages,
    _validate_python_syntax,
    analyze_crawl_flow,
    analyze_crawl_page,
    check_requirement_quality,
    classify_requirement,
    generate_script_from_test_cases,
    generate_test_cases_from_requirement,
    validate_script,
)
from app.ai.client import AzureOpenAIClient, UsageRecord
from app.models.test_script import ScriptFormat


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def ctx() -> GenerationContext:
    return GenerationContext(
        company_id=UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"),
        project_id=UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"),
        base_url="https://example.com",
        industry="Software",
        system_type="WEB",
        feature_name="Login",
    )


def _make_usage() -> UsageRecord:
    return UsageRecord(
        model="gpt-4o",
        prompt_tokens=100,
        completion_tokens=200,
        total_tokens=300,
        latency_ms=500,
        cost_estimate_usd=0.005,
    )


def _mock_client(json_return: Any) -> AzureOpenAIClient:
    client = MagicMock(spec=AzureOpenAIClient)
    client.complete_json = AsyncMock(return_value=(json_return, _make_usage()))
    client.complete = AsyncMock(return_value=("generated script content", _make_usage()))
    return client


# ---------------------------------------------------------------------------
# Cache
# ---------------------------------------------------------------------------


def test_cache_key_is_deterministic() -> None:
    k1 = _cache_key("a", "b", "c")
    k2 = _cache_key("a", "b", "c")
    assert k1 == k2


def test_cache_key_differs_on_different_input() -> None:
    assert _cache_key("x") != _cache_key("y")


def test_cache_miss_returns_none() -> None:
    assert _cache_get("nonexistent-key-xyz") is None


def test_cache_set_and_get_roundtrip() -> None:
    key = _cache_key("test", "roundtrip")
    _chains_module._cache.pop(key, None)  # ensure clean state
    _cache_set(key, {"value": 42})
    result = _cache_get(key)
    assert result == {"value": 42}


def test_cache_expired_returns_none() -> None:
    key = _cache_key("test", "ttl-expiry")
    _chains_module._cache[key] = ({"x": 1}, time.monotonic() - _CACHE_TTL - 1)
    assert _cache_get(key) is None
    assert key not in _chains_module._cache  # evicted on read


# ---------------------------------------------------------------------------
# Content safety
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "content,expected_violation",
    [
        # Clean content
        ("page.goto(process.env.BASE_URL)", None),
        # Hardcoded credential
        ("password='hunter2'", "credential"),
        ("api_key: sk-abc123defg4567hijklmn", "credential"),
        ("Authorization: Bearer eyJhbGciOiJSUzI1NiJ9.very.long.token.here.abc123", "credential"),
        # Localhost URL
        ("navigate to http://localhost:3000/login", "localhost"),
        ("http://127.0.0.1:8080/api", "localhost"),
        # PII — SSN pattern
        ("User SSN: 123-45-6789", "PII"),
    ],
)
def test_content_safety_patterns(content: str, expected_violation: str | None) -> None:
    violations = _check_content_safety(content)
    if expected_violation is None:
        assert violations == [], f"Expected no violations but got: {violations}"
    else:
        assert any(expected_violation.lower() in v.lower() for v in violations), (
            f"Expected '{expected_violation}' violation in {violations}"
        )


# ---------------------------------------------------------------------------
# Python syntax validation
# ---------------------------------------------------------------------------


def test_valid_python_returns_no_errors() -> None:
    code = "def test_login():\n    assert True\n"
    assert _validate_python_syntax(code) == []


def test_invalid_python_returns_error() -> None:
    code = "def broken(\n    pass"
    errors = _validate_python_syntax(code)
    assert len(errors) == 1
    assert "syntax" in errors[0].lower()


# ---------------------------------------------------------------------------
# validate_script orchestration
# ---------------------------------------------------------------------------


def test_validate_script_clean_python() -> None:
    code = (
        "import pytest\n\n"
        "def test_example(selenium, base_url):\n"
        "    selenium.get(base_url)\n"
    )
    errors = validate_script(code, ScriptFormat.SELENIUM_PYTHON)
    assert errors == []


def test_validate_script_flags_credential_in_python() -> None:
    code = (
        "def test_login():\n"
        "    password='mysecret'\n"
    )
    errors = validate_script(code, ScriptFormat.SELENIUM_PYTHON)
    assert any("credential" in e.lower() for e in errors)


def test_validate_script_gherkin_skips_syntax_check() -> None:
    # Gherkin has no syntax validator — should pass even with bad content
    code = "Feature: Login\n  Scenario: Happy path\n    Given I open the site\n"
    errors = validate_script(code, ScriptFormat.GHERKIN)
    assert errors == []


def test_validate_script_robot_framework_no_syntax_check() -> None:
    # Robot Framework also skips syntax check but runs safety check
    code = "*** Test Cases ***\nLogin\n    Open Browser\n"
    errors = validate_script(code, ScriptFormat.ROBOT_FRAMEWORK)
    assert errors == []


# ---------------------------------------------------------------------------
# _prompt_to_messages
# ---------------------------------------------------------------------------


def test_prompt_to_messages_renders_correctly() -> None:
    from app.ai.prompts.requirement_analysis import REQUIREMENT_QUALITY_CHECK_PROMPT

    messages = _prompt_to_messages(
        REQUIREMENT_QUALITY_CHECK_PROMPT,
        {
            "requirement_title": "User Login",
            "requirement_content": "The system shall allow users to log in.",
        },
    )
    assert isinstance(messages, list)
    assert len(messages) == 2
    roles = {m["role"] for m in messages}
    assert "system" in roles
    assert "user" in roles
    # Title injected into human message
    human_msg = next(m for m in messages if m["role"] == "user")
    assert "User Login" in human_msg["content"]


# ---------------------------------------------------------------------------
# GenerationContext defaults
# ---------------------------------------------------------------------------


def test_generation_context_defaults() -> None:
    ctx = GenerationContext(
        company_id=UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"),
        project_id=UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"),
    )
    assert ctx.base_url == "https://example.com"
    assert ctx.system_type == "WEB"
    assert ctx.industry == "Software"
    assert ctx.include_assertions is True
    assert ctx.include_negative_cases is False
    assert ctx.max_steps_per_script == 20


# ---------------------------------------------------------------------------
# check_requirement_quality
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_check_requirement_quality_happy_path(ctx: GenerationContext) -> None:
    response = {
        "quality_score": 85,
        "improvement_suggestions": ["Add acceptance criteria"],
        "missing_information": [],
        "testability_verdict": "GOOD",
        "recommended_test_count": 5,
        "dimensions": {},
    }
    client = _mock_client(response)

    result, usage = await check_requirement_quality(
        "User Login",
        "The system shall allow users to log in with email and password.",
        context=ctx,
        client=client,
    )

    assert isinstance(result, QualityCheckResult)
    assert result.quality_score == 85
    assert result.testability_verdict == "GOOD"
    assert result.recommended_test_count == 5
    assert result.improvement_suggestions == ["Add acceptance criteria"]
    assert usage.total_tokens == 300


@pytest.mark.asyncio
async def test_check_requirement_quality_uses_cache(ctx: GenerationContext) -> None:
    response = {
        "quality_score": 70,
        "improvement_suggestions": [],
        "missing_information": [],
        "testability_verdict": "POOR",
        "recommended_test_count": 2,
    }
    client = _mock_client(response)

    # First call
    r1, _ = await check_requirement_quality(
        "Cached Req", "Content A", context=ctx, client=client
    )
    # Second call — should hit cache, not call LLM again
    r2, _ = await check_requirement_quality(
        "Cached Req", "Content A", context=ctx, client=client
    )

    assert client.complete_json.call_count == 1
    assert r1.quality_score == r2.quality_score


# ---------------------------------------------------------------------------
# classify_requirement
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_classify_requirement_happy_path(ctx: GenerationContext) -> None:
    response = {
        "requirement_type": "functional",
        "priority": "HIGH",
        "business_domain": "AUTHENTICATION",
        "functional_areas": ["security"],
        "suggested_test_types": ["positive", "negative"],
        "compliance_tags": ["SOC2"],
        "estimated_complexity": "MEDIUM",
        "dependencies": [],
        "risks": [],
    }
    client = _mock_client(response)

    result, usage = await classify_requirement(
        "Login Feature",
        "Users must authenticate with email + password.",
        context=ctx,
        client=client,
    )

    assert isinstance(result, RequirementClassification)
    assert result.requirement_type == "functional"
    assert result.priority == "HIGH"
    assert result.business_domain == "AUTHENTICATION"
    assert "positive" in result.suggested_test_types


# ---------------------------------------------------------------------------
# generate_test_cases_from_requirement
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_generate_test_cases_parses_response(ctx: GenerationContext) -> None:
    response = {
        "test_cases": [
            {
                "test_case_id": "TC-001",
                "title": "Login with valid credentials",
                "description": "Happy path login",
                "preconditions": ["Account exists"],
                "test_steps": [
                    {
                        "step_number": 1,
                        "action": "Navigate to /login",
                        "expected_result": "Login page shown",
                        "input_data": None,
                    }
                ],
                "expected_outcome": "Redirected to dashboard",
                "priority": "HIGH",
                "test_type": "positive",
            },
            {
                "test_case_id": "TC-002",
                "title": "Login with invalid password",
                "description": "Negative login",
                "preconditions": ["Account exists"],
                "test_steps": [
                    {
                        "step_number": 1,
                        "action": "Enter wrong password",
                        "expected_result": "Error message shown",
                        "input_data": "wrongpass",
                    }
                ],
                "expected_outcome": "Error displayed",
                "priority": "HIGH",
                "test_type": "negative",
            },
        ],
        "coverage_summary": {"total_cases": 2},
    }
    client = _mock_client(response)

    cases, usage = await generate_test_cases_from_requirement(
        "Login",
        "Users log in with email and password.",
        context=ctx,
        client=client,
    )

    assert len(cases) == 2
    tc1 = cases[0]
    assert isinstance(tc1, TestCase)
    assert tc1.test_case_id == "TC-001"
    assert tc1.test_type == "positive"
    assert len(tc1.test_steps) == 1
    assert isinstance(tc1.test_steps[0], TestStep)
    assert tc1.test_steps[0].action == "Navigate to /login"


@pytest.mark.asyncio
async def test_generate_test_cases_empty_response(ctx: GenerationContext) -> None:
    client = _mock_client({"test_cases": []})
    cases, _ = await generate_test_cases_from_requirement(
        "Vague requirement", "TBD.", context=ctx, client=client
    )
    assert cases == []


# ---------------------------------------------------------------------------
# generate_script_from_test_cases
# ---------------------------------------------------------------------------


def _sample_test_cases() -> list[TestCase]:
    return [
        TestCase(
            test_case_id="TC-001",
            title="Login happy path",
            description="End-to-end login",
            preconditions=["User account exists"],
            test_steps=[
                TestStep(1, "Navigate to /login", "Login page shown"),
                TestStep(2, "Fill email field", "Email entered", "user@example.com"),
            ],
            expected_outcome="Dashboard shown",
            priority="HIGH",
            test_type="positive",
        )
    ]


@pytest.mark.asyncio
async def test_generate_script_playwright_ts(ctx: GenerationContext) -> None:
    expected_content = (
        "import { test, expect } from '@playwright/test';\n"
        "test.describe('Login', () => {\n"
        "  test('TC-001 Login happy path', async ({ page }) => {\n"
        "    await page.goto('https://example.com/login');\n"
        "  });\n"
        "});\n"
    )
    client = MagicMock(spec=AzureOpenAIClient)
    client.complete = AsyncMock(return_value=(expected_content, _make_usage()))

    script = await generate_script_from_test_cases(
        _sample_test_cases(),
        ScriptFormat.PLAYWRIGHT_TS,
        context=ctx,
        client=client,
    )

    assert isinstance(script, GeneratedScript)
    assert script.format == ScriptFormat.PLAYWRIGHT_TS
    assert script.test_case_count == 1
    assert "playwright/test" in script.content


@pytest.mark.asyncio
async def test_generate_script_strips_markdown_fences(ctx: GenerationContext) -> None:
    raw = "```typescript\nimport { test } from '@playwright/test';\n```"
    client = MagicMock(spec=AzureOpenAIClient)
    client.complete = AsyncMock(return_value=(raw, _make_usage()))

    script = await generate_script_from_test_cases(
        _sample_test_cases(),
        ScriptFormat.PLAYWRIGHT_TS,
        context=ctx,
        client=client,
    )
    assert "```" not in script.content
    assert script.content.startswith("import")


@pytest.mark.asyncio
async def test_generate_script_raises_on_safety_violation(ctx: GenerationContext) -> None:
    dangerous_content = (
        "import { test } from '@playwright/test';\n"
        "const password = 'hunter2';\n"
        "test('bad', async ({ page }) => { });\n"
    )
    client = MagicMock(spec=AzureOpenAIClient)
    client.complete = AsyncMock(return_value=(dangerous_content, _make_usage()))

    with pytest.raises(ValueError, match="validation"):
        await generate_script_from_test_cases(
            _sample_test_cases(),
            ScriptFormat.PLAYWRIGHT_TS,
            context=ctx,
            client=client,
        )


@pytest.mark.asyncio
async def test_generate_script_gherkin(ctx: GenerationContext) -> None:
    gherkin_content = (
        "Feature: Login\n"
        "  Scenario: Happy path\n"
        "    Given the user is on the login page\n"
        "    When the user submits valid credentials\n"
        "    Then the user sees the dashboard\n"
    )
    client = MagicMock(spec=AzureOpenAIClient)
    client.complete = AsyncMock(return_value=(gherkin_content, _make_usage()))

    script = await generate_script_from_test_cases(
        _sample_test_cases(),
        ScriptFormat.GHERKIN,
        context=ctx,
        client=client,
    )
    assert "Feature:" in script.content
    assert script.format == ScriptFormat.GHERKIN


# ---------------------------------------------------------------------------
# analyze_crawl_page
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_analyze_crawl_page_returns_requirements(ctx: GenerationContext) -> None:
    response = {
        "page_summary": "Login page",
        "requirements": [
            {
                "title": "User can submit login credentials",
                "description": "The system must allow authenticated users to provide credentials.",
                "priority": "HIGH",
                "business_domain": "AUTHENTICATION",
                "actors": ["End User"],
                "acceptance_criteria": ["Given valid creds, user is redirected"],
                "tags": ["authentication"],
            }
        ],
    }
    client = _mock_client(response)

    reqs, usage = await analyze_crawl_page(
        page_url="https://app.example.com/login",
        page_title="Login",
        elements_json='[{"type": "input", "label": "Email"}]',
        outbound_links_json='["/dashboard"]',
        context=ctx,
        client=client,
    )

    assert len(reqs) == 1
    assert reqs[0]["title"] == "User can submit login credentials"
    assert reqs[0]["priority"] == "HIGH"


# ---------------------------------------------------------------------------
# analyze_crawl_flow
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_analyze_crawl_flow_returns_test_cases(ctx: GenerationContext) -> None:
    response = {
        "flow_summary": "Login → Dashboard flow",
        "test_cases": [
            {
                "test_case_id": "TC-001",
                "title": "Complete login flow happy path",
                "description": "End-to-end test",
                "preconditions": ["User account exists"],
                "test_steps": [
                    {"step_number": 1, "action": "Go to /login", "expected_result": "Login shown", "input_data": None}
                ],
                "expected_outcome": "Dashboard shown",
                "priority": "HIGH",
                "test_type": "positive",
            }
        ],
    }
    client = _mock_client(response)

    cases, usage = await analyze_crawl_flow(
        flow_name="Login Flow",
        flow_pages=[{"url": "/login"}, {"url": "/dashboard"}],
        elements_summary="Login form, email+password inputs, submit button",
        context=ctx,
        client=client,
    )

    assert len(cases) == 1
    assert cases[0].title == "Complete login flow happy path"
    assert cases[0].test_type == "positive"
