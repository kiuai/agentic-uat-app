"""Azure OpenAI client setup via LangChain."""

from __future__ import annotations

from functools import lru_cache

from langchain_openai import AzureChatOpenAI
from openai import RateLimitError, APIStatusError

from app.config import get_settings


@lru_cache
def get_azure_chat_model(temperature: float = 0.2) -> AzureChatOpenAI:
    settings = get_settings()
    return AzureChatOpenAI(
        azure_endpoint=settings.azure_openai_endpoint,
        azure_deployment=settings.azure_openai_deployment_name,
        api_version=settings.azure_openai_api_version,
        api_key=settings.azure_openai_api_key,
        temperature=temperature,
        max_retries=settings.azure_openai_max_retries,
        request_timeout=settings.azure_openai_request_timeout,
    )
