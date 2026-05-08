"""
Azure OpenAI client with retry logic, token counting, usage logging, and
structured output support.

Usage
-----
    client = AzureOpenAIClient.from_settings()
    result = await client.complete(
        messages=[...],
        response_model=MyPydanticModel,  # enables structured output
    )
"""

from __future__ import annotations

import time
from typing import Any, TypeVar, overload

import structlog
import tiktoken
from openai import AsyncAzureOpenAI, APIConnectionError, APIStatusError, RateLimitError
from pydantic import BaseModel
from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.config import Settings, get_settings

logger = structlog.get_logger(__name__)

T = TypeVar("T", bound=BaseModel)

# Cost per 1k tokens (GPT-4o — update as pricing changes)
_INPUT_COST_PER_1K = 0.005
_OUTPUT_COST_PER_1K = 0.015

# Max tokens to allow per request — hard guardrail before sending to API
_MAX_PROMPT_TOKENS = 100_000


class UsageRecord(BaseModel):
    model: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    latency_ms: int
    cost_estimate_usd: float
    company_id: str | None = None


class AzureOpenAIClient:
    """
    Thin async wrapper around the Azure OpenAI SDK.

    - Retry: exponential backoff on RateLimitError / connection errors (max 3 attempts)
    - Token counting: tiktoken guardrail before sending
    - Usage logging: every call logged via structlog + returned as UsageRecord
    - Structured output: pass response_model= for JSON-mode Pydantic parsing
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._client = AsyncAzureOpenAI(
            azure_endpoint=settings.azure_openai_endpoint,
            api_key=settings.azure_openai_api_key,
            api_version="2024-10-01-preview",
        )
        self._deployment = settings.azure_openai_deployment_name
        try:
            self._encoder = tiktoken.encoding_for_model("gpt-4o")
        except KeyError:
            self._encoder = tiktoken.get_encoding("cl100k_base")

    @classmethod
    def from_settings(cls) -> "AzureOpenAIClient":
        return cls(get_settings())

    # ── Token counting ────────────────────────────────────────────────────

    def count_tokens(self, text: str) -> int:
        return len(self._encoder.encode(text))

    def count_messages_tokens(self, messages: list[dict[str, str]]) -> int:
        total = 0
        for msg in messages:
            total += 4  # per-message overhead
            for value in msg.values():
                total += self.count_tokens(str(value))
        return total + 2  # reply priming

    # ── Core completion ───────────────────────────────────────────────────

    async def complete(
        self,
        messages: list[dict[str, str]],
        *,
        temperature: float = 0.2,
        max_tokens: int = 4096,
        response_model: type[T] | None = None,
        company_id: str | None = None,
        json_mode: bool = False,
    ) -> tuple[str | T, UsageRecord]:
        """
        Send a chat completion request and return (content, UsageRecord).

        If response_model is provided, the API is called in JSON mode and the
        response is parsed into the given Pydantic model.
        """
        # Token guardrail
        prompt_tokens_estimate = self.count_messages_tokens(messages)
        if prompt_tokens_estimate > _MAX_PROMPT_TOKENS:
            raise ValueError(
                f"Prompt too long: ~{prompt_tokens_estimate} tokens "
                f"exceeds max {_MAX_PROMPT_TOKENS}."
            )

        use_json = response_model is not None or json_mode
        kwargs: dict[str, Any] = {
            "model": self._deployment,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if use_json:
            kwargs["response_format"] = {"type": "json_object"}

        start = time.monotonic()

        async for attempt in AsyncRetrying(
            retry=retry_if_exception_type((RateLimitError, APIConnectionError)),
            wait=wait_exponential(multiplier=1, min=2, max=30),
            stop=stop_after_attempt(3),
            reraise=True,
        ):
            with attempt:
                response = await self._client.chat.completions.create(**kwargs)

        latency_ms = round((time.monotonic() - start) * 1000)
        usage = response.usage

        cost = (
            (usage.prompt_tokens / 1000) * _INPUT_COST_PER_1K
            + (usage.completion_tokens / 1000) * _OUTPUT_COST_PER_1K
        )

        record = UsageRecord(
            model=response.model,
            prompt_tokens=usage.prompt_tokens,
            completion_tokens=usage.completion_tokens,
            total_tokens=usage.total_tokens,
            latency_ms=latency_ms,
            cost_estimate_usd=round(cost, 6),
            company_id=company_id,
        )

        logger.info(
            "openai_call",
            model=record.model,
            prompt_tokens=record.prompt_tokens,
            completion_tokens=record.completion_tokens,
            latency_ms=record.latency_ms,
            cost_usd=record.cost_estimate_usd,
            company_id=company_id,
        )

        raw_content: str = response.choices[0].message.content or ""

        if response_model is not None:
            import json
            parsed = response_model.model_validate_json(raw_content)
            return parsed, record

        return raw_content, record

    async def complete_json(
        self,
        messages: list[dict[str, str]],
        *,
        temperature: float = 0.1,
        max_tokens: int = 4096,
        company_id: str | None = None,
    ) -> tuple[Any, UsageRecord]:
        """Convenience wrapper that always returns a parsed JSON value."""
        import json
        content, record = await self.complete(
            messages,
            temperature=temperature,
            max_tokens=max_tokens,
            company_id=company_id,
            json_mode=True,
        )
        return json.loads(content), record  # type: ignore[arg-type]

    # ── Streaming ─────────────────────────────────────────────────────────

    async def stream(
        self,
        messages: list[dict[str, str]],
        *,
        temperature: float = 0.0,
        max_tokens: int = 8192,
        company_id: str | None = None,
    ):
        """
        Async generator that yields text chunks as they arrive.
        Usage is logged at stream completion.
        """
        start = time.monotonic()
        collected: list[str] = []
        prompt_tokens = self.count_messages_tokens(messages)

        async with await self._client.chat.completions.create(
            model=self._deployment,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=True,
        ) as stream:
            async for chunk in stream:
                delta = chunk.choices[0].delta.content if chunk.choices else None
                if delta:
                    collected.append(delta)
                    yield delta

        completion = "".join(collected)
        completion_tokens = self.count_tokens(completion)
        latency_ms = round((time.monotonic() - start) * 1000)
        cost = (
            (prompt_tokens / 1000) * _INPUT_COST_PER_1K
            + (completion_tokens / 1000) * _OUTPUT_COST_PER_1K
        )
        logger.info(
            "openai_stream_complete",
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            latency_ms=latency_ms,
            cost_usd=round(cost, 6),
            company_id=company_id,
        )


# Module-level singleton — re-created if settings change (test override)
_client: AzureOpenAIClient | None = None


def get_ai_client() -> AzureOpenAIClient:
    global _client
    if _client is None:
        _client = AzureOpenAIClient.from_settings()
    return _client


# LangChain-compatible wrapper (used by existing chain code)
from functools import lru_cache
from langchain_openai import AzureChatOpenAI


@lru_cache
def get_azure_chat_model(temperature: float = 0.2) -> AzureChatOpenAI:
    settings = get_settings()
    return AzureChatOpenAI(
        azure_endpoint=settings.azure_openai_endpoint,
        azure_deployment=settings.azure_openai_deployment_name,
        api_version="2024-10-01-preview",
        api_key=settings.azure_openai_api_key,
        temperature=temperature,
        max_retries=settings.azure_openai_max_retries,
        request_timeout=settings.azure_openai_request_timeout,
    )
