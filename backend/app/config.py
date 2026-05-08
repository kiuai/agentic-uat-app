"""
Application configuration loaded from environment variables.

In production, sensitive values are stored in Azure Key Vault and injected as
Container Apps secret references — they appear to the app as standard env vars.
In development, values are read directly from the .env file.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Runtime ──────────────────────────────────────────────────────────────
    environment: Literal["development", "staging", "production"] = "development"
    log_level: str = "INFO"
    secret_key: str = Field(min_length=32)
    allowed_origins: list[str] = ["http://localhost:5173", "http://localhost:3000"]

    # ── Azure AD / Entra ID ──────────────────────────────────────────────────
    azure_client_id: str
    azure_tenant_id: str
    azure_client_secret: str = ""

    # ── Azure OpenAI ─────────────────────────────────────────────────────────
    azure_openai_endpoint: str = ""
    azure_openai_api_key: str = ""
    azure_openai_deployment_name: str = "kaats-gpt4o"
    azure_openai_api_version: str = "2024-08-01-preview"
    azure_openai_max_retries: int = 3
    azure_openai_request_timeout: int = 120

    # ── Azure SQL ─────────────────────────────────────────────────────────────
    azure_sql_server: str = "localhost,1433"
    azure_sql_database: str = "kaats_dev"
    azure_sql_username: str = "sa"
    azure_sql_password: str = ""
    # When set, overrides the individual fields above
    azure_sql_connection_string: str = ""

    # ── Azure Cosmos DB ──────────────────────────────────────────────────────
    azure_cosmos_endpoint: str = "https://localhost:8081"
    azure_cosmos_key: str = ""
    azure_cosmos_database: str = "kaats"

    # ── Azure Service Bus ────────────────────────────────────────────────────
    azure_service_bus_connection_string: str = ""
    azure_service_bus_ai_jobs_topic: str = "ai-jobs"
    azure_service_bus_crawl_jobs_topic: str = "crawl-jobs"
    azure_service_bus_result_events_topic: str = "result-events"
    azure_service_bus_subscription_name: str = "kaats-worker"

    # ── Azure Blob Storage ───────────────────────────────────────────────────
    azure_storage_account_name: str = "devstoreaccount1"
    azure_storage_account_key: str = ""
    azure_storage_connection_string: str = ""

    # ── Azure Key Vault ──────────────────────────────────────────────────────
    azure_key_vault_url: str = ""

    # ── Application Insights ─────────────────────────────────────────────────
    applicationinsights_connection_string: str = ""

    @field_validator("allowed_origins", mode="before")
    @classmethod
    def parse_origins(cls, v: str | list[str]) -> list[str]:
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        return v

    @model_validator(mode="after")
    def build_sql_connection_string(self) -> "Settings":
        if not self.azure_sql_connection_string:
            self.azure_sql_connection_string = (
                f"DRIVER={{ODBC Driver 18 for SQL Server}};"
                f"SERVER={self.azure_sql_server};"
                f"DATABASE={self.azure_sql_database};"
                f"UID={self.azure_sql_username};"
                f"PWD={self.azure_sql_password};"
                f"TrustServerCertificate=yes;"
                f"Encrypt=yes;"
            )
        return self

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    @property
    def openapi_enabled(self) -> bool:
        return not self.is_production

    @property
    def sqlalchemy_database_url(self) -> str:
        return f"mssql+aioodbc:///?odbc_connect={self.azure_sql_connection_string}"

    @property
    def entra_jwks_uri(self) -> str:
        return (
            f"https://login.microsoftonline.com/{self.azure_tenant_id}"
            f"/discovery/v2.0/keys"
        )

    @property
    def entra_issuer(self) -> str:
        return f"https://sts.windows.net/{self.azure_tenant_id}/"


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
