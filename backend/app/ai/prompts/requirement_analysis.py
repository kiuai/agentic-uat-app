"""Prompts for requirement quality checking and classification."""

from __future__ import annotations

from langchain_core.prompts import ChatPromptTemplate

# ---------------------------------------------------------------------------
# 1. Requirement Quality Check
# ---------------------------------------------------------------------------

REQUIREMENT_QUALITY_CHECK_PROMPT = ChatPromptTemplate.from_messages([
    (
        "system",
        """You are a senior business analyst and QA architect who evaluates
software requirements for quality. You assess completeness, testability,
and ambiguity. Output structured JSON only.""",
    ),
    (
        "human",
        """Analyze the following software requirement for quality.

Title: {requirement_title}
Content:
---
{requirement_content}
---

Evaluate on these dimensions:
1. Completeness   — does it specify what, who, when, and under what conditions?
2. Testability    — can acceptance criteria be written and verified?
3. Unambiguity    — is it free of vague terms (e.g. "fast", "easy", "appropriate")?
4. Atomicity      — does it describe a single, coherent capability?
5. Traceability   — can it be linked to a business goal or user story?

Return a JSON object with this exact structure:
{{
  "quality_score": 85,
  "dimensions": {{
    "completeness": {{ "score": 90, "issues": [] }},
    "testability": {{ "score": 80, "issues": ["Missing acceptance criteria"] }},
    "unambiguity": {{ "score": 85, "issues": ["'user-friendly' is vague"] }},
    "atomicity": {{ "score": 90, "issues": [] }},
    "traceability": {{ "score": 80, "issues": ["No reference to business goal"] }}
  }},
  "improvement_suggestions": [
    "Add explicit acceptance criteria: e.g. 'Login must complete within 2 seconds'",
    "Replace 'user-friendly' with specific usability criteria"
  ],
  "missing_information": ["Error states and messages", "Edge case: expired session"],
  "testability_verdict": "GOOD",
  "recommended_test_count": 6
}}

quality_score: integer 0–100 (average of dimension scores)
testability_verdict: one of EXCELLENT / GOOD / POOR / UNTESTABLE""",
    ),
])

# ---------------------------------------------------------------------------
# 2. Requirement Classification
# ---------------------------------------------------------------------------

REQUIREMENT_CLASSIFICATION_PROMPT = ChatPromptTemplate.from_messages([
    (
        "system",
        """You are a requirements classification expert.
Given a software requirement, classify it and recommend test coverage.
Output JSON only.""",
    ),
    (
        "human",
        """Classify the following software requirement.

Title: {requirement_title}
Content:
---
{requirement_content}
---

Return a JSON object with this exact structure:
{{
  "requirement_type": "functional",
  "priority": "HIGH",
  "business_domain": "AUTHENTICATION",
  "functional_areas": ["user management", "security"],
  "suggested_test_types": ["positive", "negative", "boundary", "security"],
  "compliance_tags": ["SOC2", "GDPR"],
  "estimated_complexity": "MEDIUM",
  "dependencies": ["User registration flow", "Session management"],
  "risks": ["Brute force attacks if rate limiting not implemented"]
}}

requirement_type: functional | non-functional | constraint | assumption
priority: CRITICAL | HIGH | MEDIUM | LOW
estimated_complexity: LOW | MEDIUM | HIGH | VERY_HIGH""",
    ),
])

# Backward-compat alias
analyze_requirement_prompt = REQUIREMENT_QUALITY_CHECK_PROMPT
