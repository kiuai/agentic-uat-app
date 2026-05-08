from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "dev"
    app_secret_key: str = "change_me"
    access_token_expire_minutes: int = 120

    database_url: str = "sqlite:///./local.db"

    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str = "redis://localhost:6379/0"
    celery_result_backend: str = "redis://localhost:6379/0"

    evidence_dir: str = "./evidence"

    llm_provider: str = "stub"
    openai_api_key: str | None = None
    openai_model: str = "gpt-4.1-mini"
    azure_openai_endpoint: str | None = None
    azure_openai_api_key: str | None = None
    azure_openai_api_version: str | None = None
    azure_openai_deployment: str | None = None

settings = Settings()
