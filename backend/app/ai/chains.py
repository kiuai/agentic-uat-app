"""
LangChain chains for the test generation pipeline.

Pipeline stages:
1. decompose  — split requirements into atomic test scenarios
2. generate   — for each scenario, generate structured test steps
3. format     — convert to target framework script text
4. validate   — parse generated scripts to verify syntax
"""

from __future__ import annotations

import json
from typing import Any

import structlog
from langchain_core.output_parsers import JsonOutputParser, StrOutputParser
from langchain_core.runnables import RunnableSequence

from app.ai.client import get_azure_chat_model
from app.ai.prompts.test_generation import (
    decompose_prompt,
    format_playwright_ts_prompt,
    generate_steps_prompt,
)

logger = structlog.get_logger(__name__)


def build_decompose_chain() -> RunnableSequence:
    """Stage 1: Requirement → list of test scenarios."""
    model = get_azure_chat_model(temperature=0.1)
    return decompose_prompt | model | JsonOutputParser()


def build_generate_steps_chain() -> RunnableSequence:
    """Stage 2: Scenario → structured test steps."""
    model = get_azure_chat_model(temperature=0.2)
    return generate_steps_prompt | model | JsonOutputParser()


def build_format_playwright_ts_chain() -> RunnableSequence:
    """Stage 3 (Playwright TS): Structured test steps → TypeScript code."""
    model = get_azure_chat_model(temperature=0.0)
    return format_playwright_ts_prompt | model | StrOutputParser()


async def run_decompose(
    requirement_content: str,
    company_name: str = "KAATS",
    industry: str = "Software",
) -> list[dict[str, Any]]:
    chain = build_decompose_chain()
    result = await chain.ainvoke({
        "requirement_content": requirement_content,
        "company_name": company_name,
        "industry": industry,
    })
    if not isinstance(result, list):
        raise ValueError(f"Decompose chain returned unexpected type: {type(result)}")
    logger.info("decompose_complete", scenario_count=len(result))
    return result


async def run_generate_steps(
    scenario: dict[str, Any],
    app_description: str = "Web application",
) -> dict[str, Any]:
    chain = build_generate_steps_chain()
    return await chain.ainvoke({
        "scenario_id": scenario.get("scenario_id", "SCN-001"),
        "scenario_title": scenario.get("title", ""),
        "preconditions": json.dumps(scenario.get("preconditions", [])),
        "actors": json.dumps(scenario.get("actors", [])),
        "app_description": app_description,
    })


async def run_format_playwright_ts(
    test_case: dict[str, Any],
    base_url: str = "https://example.com",
) -> str:
    chain = build_format_playwright_ts_chain()
    return await chain.ainvoke({
        "test_case_json": json.dumps(test_case, indent=2),
        "base_url": base_url,
    })
