"""Prompts for converting crawler output to test script candidates."""

from __future__ import annotations

from langchain_core.prompts import ChatPromptTemplate

CRAWL_ANALYSIS_SYSTEM = """You are a test automation expert analyzing web application UI flows.
Given a map of discovered pages and interactions, generate test scenario candidates.
Output JSON only."""

CRAWL_ANALYSIS_HUMAN = """Analyze the following web application crawl map and generate test scenarios.

Crawl map:
---
{crawl_map_json}
---

For each discovered user flow, generate a test scenario with:
- A descriptive title
- The sequence of steps (URL, action, element, expected result)
- The applicable test type (POSITIVE, NEGATIVE, EDGE_CASE)

Output a JSON array of test scenarios in the same format as the test generation pipeline."""

crawl_analysis_prompt = ChatPromptTemplate.from_messages([
    ("system", CRAWL_ANALYSIS_SYSTEM),
    ("human", CRAWL_ANALYSIS_HUMAN),
])
