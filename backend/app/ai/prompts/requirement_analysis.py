"""Prompts for requirement analysis and summarization."""

from __future__ import annotations

from langchain_core.prompts import ChatPromptTemplate

ANALYZE_SYSTEM = """You are a business analyst expert at extracting structured information
from software requirements documents. Output JSON only."""

ANALYZE_HUMAN = """Analyze the following requirement document and extract structured information.

Document:
---
{content}
---

Output a JSON object with:
{{
  "summary": "2-3 sentence summary",
  "functional_requirements": ["list", "of", "functional", "requirements"],
  "non_functional_requirements": ["list of NFRs"],
  "actors": ["User", "Admin"],
  "business_domain": "detected domain (e.g., FINANCE, HR, INVENTORY)",
  "suggested_test_count": 5,
  "complexity": "LOW|MEDIUM|HIGH"
}}"""

analyze_requirement_prompt = ChatPromptTemplate.from_messages([
    ("system", ANALYZE_SYSTEM),
    ("human", ANALYZE_HUMAN),
])
