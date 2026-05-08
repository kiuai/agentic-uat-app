"""
Prompt templates for AI test generation pipeline.

Templates follow a consistent pattern:
  SYSTEM message — role, output format constraints, conventions
  HUMAN message  — the specific task with placeholders

All prompts instruct the model to output JSON only (no markdown fences).
"""

from __future__ import annotations

from langchain_core.prompts import ChatPromptTemplate

# ---------------------------------------------------------------------------
# 1. Requirement → Test Cases
# ---------------------------------------------------------------------------

REQUIREMENT_TO_TEST_CASES_PROMPT = ChatPromptTemplate.from_messages([
    (
        "system",
        """You are a senior QA engineer specializing in acceptance test design.
You produce structured JSON only. Never output markdown, prose, or code fences.
Industry: {industry}. System type: {system_type}.""",
    ),
    (
        "human",
        """Given the software requirement below, generate a comprehensive set of test cases.
Cover: happy path, negative cases, boundary conditions, and edge cases.
Include both functional and UX validations.

Requirement title: {requirement_title}
Requirement description:
---
{requirement_content}
---

Business domain: {business_domain}
Priority: {priority}

Output a JSON object with this exact structure:
{{
  "test_cases": [
    {{
      "test_case_id": "TC-001",
      "title": "Short descriptive title",
      "description": "What this test validates",
      "preconditions": ["User is authenticated", "Feature flag X is enabled"],
      "test_steps": [
        {{
          "step_number": 1,
          "action": "Navigate to /login",
          "expected_result": "Login page renders with email and password fields",
          "input_data": null
        }}
      ],
      "expected_outcome": "User is redirected to dashboard with success message",
      "priority": "HIGH",
      "test_type": "positive"
    }}
  ],
  "coverage_summary": {{
    "total_cases": 5,
    "positive_cases": 2,
    "negative_cases": 2,
    "boundary_cases": 1,
    "missing_coverage": ["performance under load", "concurrent sessions"]
  }}
}}

test_type must be one of: positive, negative, boundary, performance
priority must be one of: CRITICAL, HIGH, MEDIUM, LOW""",
    ),
])

# ---------------------------------------------------------------------------
# 2. Test Cases → Playwright TypeScript
# ---------------------------------------------------------------------------

TEST_CASES_TO_PLAYWRIGHT_PROMPT = ChatPromptTemplate.from_messages([
    (
        "system",
        """You are an expert Playwright TypeScript test automation engineer.
Generate complete, runnable TypeScript test files. Follow these conventions:
- Use async/await throughout; never use .then()
- Prefer ARIA locators: page.getByRole(), page.getByLabel(), page.getByText()
- Use expect() after every significant action
- Structure: imports → test.describe() → beforeEach/afterEach → test() per case
- Add await page.waitForLoadState('networkidle') after navigations
- Never use hard-coded timeouts (page.waitForTimeout is forbidden)
- Never hardcode credentials — use process.env.TEST_USER / process.env.TEST_PASS
- Output valid TypeScript only. No markdown fences. No explanations.""",
    ),
    (
        "human",
        """Convert these test cases into a complete Playwright TypeScript test file.

Base URL: {base_url}
Page/Feature under test: {feature_name}

Test cases:
{test_cases_json}

The file must include:
1. Import statement: import {{ test, expect }} from '@playwright/test';
2. A test.describe('{feature_name}', () => {{ ... }}) block
3. A beforeEach that navigates to the starting URL
4. One test() function per test case, named after the test_case_id and title
5. Full step-by-step implementation of each test_step
6. Meaningful expect() assertions matching expected_result values""",
    ),
])

# ---------------------------------------------------------------------------
# 3. Test Cases → Selenium Python
# ---------------------------------------------------------------------------

TEST_CASES_TO_SELENIUM_PROMPT = ChatPromptTemplate.from_messages([
    (
        "system",
        """You are a Selenium Python test automation expert using pytest-selenium.
Generate complete, runnable Python test files following these conventions:
- Use pytest fixtures: selenium, base_url
- Use Page Object Model pattern: define a minimal page class above the tests
- Use WebDriverWait with explicit expected_conditions (no time.sleep)
- Prefer CSS selectors or accessible name locators
- Never hardcode credentials — use os.environ
- Output valid Python only. No markdown. No explanations.""",
    ),
    (
        "human",
        """Convert these test cases into a complete Selenium Python pytest file.

Base URL: {base_url}
Feature: {feature_name}

Test cases:
{test_cases_json}

Structure:
1. Imports (pytest, selenium, os, time, typing)
2. A minimal Page Object class for the feature
3. One test function per test case prefixed with test_
4. Fixtures: selenium (provided by pytest-selenium), base_url""",
    ),
])

# ---------------------------------------------------------------------------
# 4. Test Cases → Pytest (pure, no Selenium)
# ---------------------------------------------------------------------------

TEST_CASES_TO_PYTEST_PROMPT = ChatPromptTemplate.from_messages([
    (
        "system",
        """You are a pytest expert writing API and integration tests.
Generate complete pytest files using httpx.AsyncClient or requests.
Conventions:
- Use @pytest.mark.asyncio for async tests
- Use @pytest.fixture for shared setup
- Use @pytest.mark.parametrize for data-driven cases where applicable
- Assert on HTTP status codes and response body fields
- Never hardcode credentials
- Output valid Python only. No markdown. No explanations.""",
    ),
    (
        "human",
        """Convert these test cases into a pytest test file for API/integration testing.

Base URL: {base_url}
Feature: {feature_name}

Test cases:
{test_cases_json}

Each test case should validate the API contract described in the test steps.""",
    ),
])

# ---------------------------------------------------------------------------
# 5. Test Cases → Robot Framework
# ---------------------------------------------------------------------------

TEST_CASES_TO_ROBOT_FRAMEWORK_PROMPT = ChatPromptTemplate.from_messages([
    (
        "system",
        """You are a Robot Framework expert.
Generate complete .robot files following these conventions:
- Use SeleniumLibrary or Browser library keywords
- Define reusable Keywords in a *** Keywords *** section
- Use *** Settings ***, *** Variables ***, *** Test Cases ***, *** Keywords ***
- Variable names in ALL_CAPS with $ prefix: ${BASE_URL}
- Use Suite Setup / Suite Teardown for browser lifecycle
- Never hardcode credentials — use environment variables via Get Environment Variable
- Output valid Robot Framework syntax only. No markdown. No explanations.""",
    ),
    (
        "human",
        """Convert these test cases into a Robot Framework .robot file.

Base URL: {base_url}
Feature: {feature_name}

Test cases:
{test_cases_json}

The file must include all four standard sections.
Each test case maps to one entry in *** Test Cases ***.""",
    ),
])

# ---------------------------------------------------------------------------
# 6. Test Cases → Gherkin
# ---------------------------------------------------------------------------

TEST_CASES_TO_GHERKIN_PROMPT = ChatPromptTemplate.from_messages([
    (
        "system",
        """You are a BDD expert writing Gherkin feature files.
Follow these conventions:
- Feature: one feature per file
- Scenario or Scenario Outline per test case
- Use Background: for shared preconditions
- Use Scenario Outline + Examples: for parametrized cases
- Steps must follow Given (context) / When (action) / Then (assertion) / And / But
- Steps must be declarative, not imperative: avoid 'click', prefer 'the user submits'
- Output valid Gherkin (.feature) syntax only. No markdown. No explanations.""",
    ),
    (
        "human",
        """Convert these test cases into a Gherkin .feature file.

Feature name: {feature_name}

Test cases:
{test_cases_json}

Map each test_case to a Scenario or Scenario Outline.
Map preconditions to Background or Given steps.
Map test_steps to When/Then steps.""",
    ),
])

# ---------------------------------------------------------------------------
# Backward-compat aliases for chains.py that import the old names
# ---------------------------------------------------------------------------

decompose_prompt = REQUIREMENT_TO_TEST_CASES_PROMPT
generate_steps_prompt = TEST_CASES_TO_PLAYWRIGHT_PROMPT
format_playwright_ts_prompt = TEST_CASES_TO_PLAYWRIGHT_PROMPT
