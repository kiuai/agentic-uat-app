from __future__ import annotations

import json
from typing import Any
import httpx

from app.settings import settings
from app.schemas import TestCase
from app.llm.prompts import SYSTEM, user_prompt

# -------- Deterministic fallback (no network) --------

def _pick_best(elements: list[dict], role: str, limit: int = 3) -> list[dict]:
    pref = [e for e in elements if e.get("role")==role and (e.get("selector") or "").startswith("[data-testid=")]
    if not pref:
        pref = [e for e in elements if e.get("role")==role]
    return pref[:limit]

def generate_tests_stub(
    requirements: list[dict],
    base_url: str,
    pages: list[dict],
    elements: list[dict],
    llm_cfg: dict | None = None,
) -> list[TestCase]:
    desc = requirements[0]["text"].strip() if requirements else ""
    short_desc = (desc[:60] + "…") if len(desc) > 60 else desc
    tests: list[TestCase] = []
    tests.append(TestCase(
        test_id="UAT-001",
        title=f"Manual: {short_desc}" if short_desc else "Smoke: load application landing page",
        objective=desc if desc else f"Verify the base URL loads and remains within {base_url}",
        preconditions=[],
        data={},
        risk="Low",
        requirement_ids=[requirements[0]["req_id"]] if requirements else [],
        steps=[
            {"index": 1, "action": "goto", "selector": {"url": base_url}, "critical": True},
            {"index": 2, "action": "assert_url_contains", "selector": {"contains": base_url}, "critical": True},
        ],
    ))

    inputs = _pick_best(elements, "input", 1)
    buttons = _pick_best(elements, "button", 1)

    steps = [{"index": 1, "action": "goto", "selector": {"url": base_url}, "critical": True}]
    i = 2
    if inputs:
        steps.append({"index": i, "action": "fill_css", "selector": {"css": inputs[0]["selector"]}, "input": "test", "critical": True}); i += 1
    if buttons:
        steps.append({"index": i, "action": "click_css", "selector": {"css": buttons[0]["selector"]}, "critical": True}); i += 1
    steps.append({"index": i, "action": "assert_url_contains", "selector": {"contains": base_url}, "critical": False})

    tests.append(TestCase(
        test_id="UAT-002",
        title="Basic interaction: exercise one control",
        objective="Perform one safe interaction using discovered selectors and capture evidence.",
        preconditions=[],
        data={},
        risk="Medium",
        requirement_ids=[requirements[1]["req_id"]] if len(requirements)>1 else ([requirements[0]["req_id"]] if requirements else []),
        steps=steps,
    ))
    return tests

# -------- OpenAI (Responses API) --------

def _schema() -> dict[str, Any]:
    # JSON Schema for structured output: { tests: [TestCase...] }
    return {
        "type": "object",
        "properties": {
            "tests": {
                "type": "array",
                "minItems": 1,
                "maxItems": 20,
                "items": {
                    "type": "object",
                    "properties": {
                        "test_id": {"type":"string", "minLength": 3},
                        "title": {"type":"string", "minLength": 3},
                        "objective": {"type":"string", "minLength": 3},
                        "preconditions": {"type":"array", "items":{"type":"string"}},
                        "data": {"type":"object"},
                        "risk": {"type":"string", "enum":["Low","Medium","High"]},
                        "requirement_ids": {"type":"array", "items":{"type":"string"}},
                        "steps": {
                            "type":"array",
                            "minItems": 1,
                            "maxItems": 30,
                            "items": {
                                "type":"object",
                                "properties": {
                                    "index": {"type":"integer", "minimum": 1, "maximum": 60},
                                    "action": {"type":"string", "enum":[
                                        "goto","click_css","fill_css","select_css",
                                        "assert_url_contains","assert_text_contains","wait_for_css"
                                    ]},
                                    "selector": {"type":"object"},
                                    "input": {"type":["string","null"]},
                                    "expect": {"type":["string","null"]},
                                    "critical": {"type":"boolean"}
                                },
                                "required":["index","action","selector","critical"],
                                "additionalProperties": False
                            }
                        }
                    },
                    "required":["test_id","title","objective","preconditions","data","risk","requirement_ids","steps"],
                    "additionalProperties": False
                }
            }
        },
        "required":["tests"],
        "additionalProperties": False
    }

def _extract_output_text(resp_json: dict) -> str:
    # Responses API: resp_json["output"] is a list; find message output_text blocks.
    out = resp_json.get("output", [])
    texts = []
    for item in out:
        if item.get("type") == "message":
            for c in item.get("content", []):
                if c.get("type") == "output_text":
                    texts.append(c.get("text",""))
    return "\n".join(texts).strip()

def generate_tests_openai(
    requirements: list[dict],
    base_url: str,
    pages: list[dict],
    elements: list[dict],
    llm_cfg: dict | None = None,
) -> list[TestCase]:
    provider = ((llm_cfg or {}).get("provider") or settings.llm_provider or "stub").lower()
    use_azure = provider == "azure"
    if use_azure:
        if not (settings.azure_openai_endpoint and settings.azure_openai_api_key and settings.azure_openai_api_version and settings.azure_openai_deployment):
            raise RuntimeError("AZURE_OPENAI_* is not fully set")
    else:
        if not settings.openai_api_key:
            raise RuntimeError("OPENAI_API_KEY is not set")

    model = (llm_cfg or {}).get("model") or settings.openai_model
    if use_azure:
        model = settings.azure_openai_deployment or model
    temperature = (llm_cfg or {}).get("temperature")
    if temperature is None:
        temperature = 0.2
    max_output_tokens = (llm_cfg or {}).get("max_output_tokens")
    if max_output_tokens is None:
        max_output_tokens = 2500
    strict_json = (llm_cfg or {}).get("strict_json")
    if strict_json is None:
        strict_json = True

    payload = {
        "model": model,
        "input": [
            {"role":"system", "content": SYSTEM},
            {"role":"user", "content": user_prompt(requirements, base_url, pages, elements)},
        ],
        "text": {
            "format": {
                "type": "json_schema",
                "name": "uat_tests",
                "strict": bool(strict_json),
                "schema": _schema(),
            }
        },
        "temperature": float(temperature),
        "max_output_tokens": int(max_output_tokens),
        "store": False,
    }

    if use_azure:
        endpoint = settings.azure_openai_endpoint.rstrip("/")
        url = f"{endpoint}/openai/deployments/{settings.azure_openai_deployment}/responses?api-version={settings.azure_openai_api_version}"
        headers = {"api-key": settings.azure_openai_api_key, "Content-Type":"application/json"}
    else:
        url = "https://api.openai.com/v1/responses"
        headers = {"Authorization": f"Bearer {settings.openai_api_key}", "Content-Type":"application/json"}
    with httpx.Client(timeout=60) as client:
        r = client.post(url, headers=headers, json=payload)
        r.raise_for_status()
        data = r.json()

    txt = _extract_output_text(data)
    obj = json.loads(txt) if txt else data.get("output_json")
    if obj is None:
        raise RuntimeError("No JSON returned from model")

    tests = [TestCase(**t) for t in obj["tests"]]
    return tests

def generate_tests(
    requirements: list[dict],
    base_url: str,
    pages: list[dict],
    elements: list[dict],
    llm_cfg: dict | None = None,
) -> list[TestCase]:
    provider = ((llm_cfg or {}).get("provider") or settings.llm_provider or "stub").lower()
    if provider in ("openai", "azure"):
        return generate_tests_openai(requirements, base_url, pages, elements, llm_cfg)
    # fallback
    return generate_tests_stub(requirements, base_url, pages, elements, llm_cfg)
