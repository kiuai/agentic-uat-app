from __future__ import annotations
import json

SYSTEM = """You are a senior Validation / UAT analyst.

You will propose user-acceptance tests for a web application.
Rules:
- Produce ONLY valid JSON that matches the provided JSON Schema.
- Tests must be user-centric, atomic, and traceable to requirement IDs.
- Use ONLY selectors provided in the 'Allowed selectors' list.
- Do NOT invent selectors, pages, features, APIs, or data.
- Avoid destructive actions (delete, remove, reset, admin changes) unless a requirement explicitly demands it.
- Mark evidence-critical steps with critical=true (navigation, submit, confirmation).
"""

def user_prompt(requirements: list[dict], base_url: str, pages: list[dict], elements: list[dict]) -> str:
    # Keep prompt compact; pass selectors with labels/roles.
    allowed = [
        {"selector": e.get("selector"), "role": e.get("role"), "label": e.get("label"), "type": e.get("type")}
        for e in elements
        if e.get("selector")
    ]

    return """Application base URL: {base_url}

Requirements (use req_id values for traceability):
{reqs}

Discovered pages (most recent):
{pages}

Allowed selectors (ONLY use these in steps.selector.css or steps.selector.role):
{allowed}

Return 5-12 UAT test cases that collectively cover as many requirements as possible.
Each test should include:
- test_id (e.g., UAT-001)
- title
- objective
- preconditions (list)
- data (object)
- risk (Low/Medium/High)
- requirement_ids (list)
- steps: ordered list with action in {goto, click_css, fill_css, select_css, assert_url_contains, assert_text_contains, wait_for_css}

For selector fields:
- If using click/fill/select/wait/assert_text, set selector.css to one of the Allowed selectors.
- For goto/assert_url_contains, use selector.url / selector.contains.

Make expected results explicit using assert_* steps.
""".format(
        base_url=base_url,
        reqs=json.dumps(requirements, ensure_ascii=False, indent=2)[:12000],
        pages=json.dumps(pages, ensure_ascii=False, indent=2)[:6000],
        allowed=json.dumps(allowed, ensure_ascii=False, indent=2)[:12000],
    )
