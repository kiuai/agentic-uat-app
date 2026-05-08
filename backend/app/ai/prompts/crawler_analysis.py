"""Prompts for converting crawler output to requirements and test cases."""

from __future__ import annotations

from langchain_core.prompts import ChatPromptTemplate

# ---------------------------------------------------------------------------
# 1. Crawled Page → Business Requirements
# ---------------------------------------------------------------------------

CRAWL_PAGE_TO_REQUIREMENTS_PROMPT = ChatPromptTemplate.from_messages([
    (
        "system",
        """You are a business analyst who reverse-engineers software requirements
from observed UI elements and page interactions.
You produce structured JSON only. No markdown, no prose.""",
    ),
    (
        "human",
        """Given the following crawled web page data, infer the business requirements
that this page fulfils.

Page URL: {page_url}
Page title: {page_title}
UI elements discovered:
{elements_json}

Interaction map (navigation paths observed from this page):
{outbound_links_json}

Infer requirements at the feature level — not at the UI implementation level.
Focus on: what business capability does this page provide? Who uses it? What
are the success and failure conditions?

Return a JSON object:
{{
  "page_summary": "Brief description of what this page does",
  "requirements": [
    {{
      "title": "User can submit login credentials",
      "description": "The system must allow authenticated users to provide their email
and password to establish a session. The form must validate inputs client-side
and display clear error messages for invalid credentials.",
      "priority": "HIGH",
      "business_domain": "AUTHENTICATION",
      "actors": ["End User"],
      "acceptance_criteria": [
        "Given a valid email/password, the user is redirected to dashboard",
        "Given invalid credentials, an error message is displayed within 500ms",
        "Given 5 failed attempts, the account is temporarily locked"
      ],
      "tags": ["authentication", "security", "regression"]
    }}
  ]
}}

Generate 2–5 requirements per page. Priority: CRITICAL | HIGH | MEDIUM | LOW""",
    ),
])

# ---------------------------------------------------------------------------
# 2. Page Flow → Test Cases
# ---------------------------------------------------------------------------

CRAWL_FLOW_TO_TEST_CASES_PROMPT = ChatPromptTemplate.from_messages([
    (
        "system",
        """You are a senior QA engineer who generates test cases from observed
user flows in a web application.
You produce structured JSON only. No markdown, no prose.""",
    ),
    (
        "human",
        """Given the following sequence of pages forming a user flow, generate test cases
that cover the happy path, common error paths, and boundary conditions.

Application name: {application_name}
Flow name: {flow_name}
Flow pages (in order):
{flow_pages_json}

For each page in the flow, the following elements were observed:
{elements_summary}

Generate test cases that:
1. Cover the complete happy path end-to-end
2. Cover each major error condition (invalid input, unauthorised access, etc.)
3. Cover boundary conditions (empty form, max-length input, special characters)
4. Are independent and repeatable

Return a JSON object:
{{
  "flow_summary": "Brief description of the user flow",
  "test_cases": [
    {{
      "test_case_id": "TC-001",
      "title": "Complete {flow_name} happy path",
      "description": "End-to-end test of the primary success scenario",
      "preconditions": ["User account exists", "User is not authenticated"],
      "test_steps": [
        {{
          "step_number": 1,
          "action": "Navigate to {flow_name} start URL",
          "expected_result": "First page of the flow is displayed",
          "input_data": null
        }}
      ],
      "expected_outcome": "Flow completes successfully",
      "priority": "HIGH",
      "test_type": "positive"
    }}
  ]
}}

test_type: positive | negative | boundary | performance
priority: CRITICAL | HIGH | MEDIUM | LOW""",
    ),
])

# Backward-compat alias
crawl_analysis_prompt = CRAWL_PAGE_TO_REQUIREMENTS_PROMPT
