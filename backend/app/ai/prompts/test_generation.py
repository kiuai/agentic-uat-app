"""Prompt templates for AI test generation pipeline."""

from __future__ import annotations

from langchain_core.prompts import ChatPromptTemplate, SystemMessagePromptTemplate, HumanMessagePromptTemplate

DECOMPOSE_SYSTEM = """You are an expert software test engineer specializing in acceptance test design.
You produce structured JSON only. Do not produce markdown, prose, or explanation outside the JSON.
Industry context: {industry}. Company: {company_name}."""

DECOMPOSE_HUMAN = """Decompose the following software requirements into individual, atomic test scenarios.
Each scenario must be independently testable and cover exactly one acceptance criterion.

Requirements:
---
{requirement_content}
---

Output a JSON array with this exact structure:
[
  {{
    "scenario_id": "SCN-001",
    "title": "Short descriptive title",
    "preconditions": ["User is logged in", "Product exists in catalog"],
    "actors": ["End User"],
    "priority": "HIGH",
    "test_type": "POSITIVE"
  }}
]

test_type must be one of: POSITIVE, NEGATIVE, EDGE_CASE
priority must be one of: HIGH, MEDIUM, LOW"""

GENERATE_STEPS_SYSTEM = """You are an expert test automation engineer.
You produce structured JSON test cases. Do not produce markdown or prose outside the JSON.
Target application: {app_description}."""

GENERATE_STEPS_HUMAN = """Generate detailed test steps for the following test scenario.
Each step must be a specific, executable user action.

Scenario: {scenario_title}
Preconditions: {preconditions}
Actors: {actors}

Output a JSON object with this exact structure:
{{
  "scenario_id": "{scenario_id}",
  "title": "{scenario_title}",
  "steps": [
    {{
      "step_number": 1,
      "action": "navigate",
      "description": "Navigate to the login page",
      "target": "/login",
      "input_data": null,
      "expected_result": "Login page is displayed with email and password fields"
    }}
  ],
  "test_data": {{}},
  "expected_final_state": "User is authenticated and redirected to dashboard"
}}"""

FORMAT_PLAYWRIGHT_TS_SYSTEM = """You are a Playwright test automation expert.
Generate TypeScript Playwright test code. Follow these conventions:
- Use async/await throughout
- Use page.getByRole(), page.getByLabel(), page.getByText() locators (prefer ARIA over CSS)
- Include meaningful expect() assertions after each major action
- Use test.describe() and test() structure
- Add page.waitForLoadState('networkidle') after navigation actions
- Do NOT use hard-coded timeouts (no page.waitForTimeout)"""

FORMAT_PLAYWRIGHT_TS_HUMAN = """Convert this test scenario to a Playwright TypeScript test:

{test_case_json}

Base URL variable: {base_url}

Output only valid TypeScript code. No explanations."""

decompose_prompt = ChatPromptTemplate.from_messages([
    SystemMessagePromptTemplate.from_template(DECOMPOSE_SYSTEM),
    HumanMessagePromptTemplate.from_template(DECOMPOSE_HUMAN),
])

generate_steps_prompt = ChatPromptTemplate.from_messages([
    SystemMessagePromptTemplate.from_template(GENERATE_STEPS_SYSTEM),
    HumanMessagePromptTemplate.from_template(GENERATE_STEPS_HUMAN),
])

format_playwright_ts_prompt = ChatPromptTemplate.from_messages([
    SystemMessagePromptTemplate.from_template(FORMAT_PLAYWRIGHT_TS_SYSTEM),
    HumanMessagePromptTemplate.from_template(FORMAT_PLAYWRIGHT_TS_HUMAN),
])
