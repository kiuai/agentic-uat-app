from __future__ import annotations

import uuid
from typing import Any

from pydantic import BaseModel, Field

from app.models.crawl_job import CrawlAuthType, CrawlerType
from app.models.test_script import ScriptFormat


class GenerationConfig(BaseModel):
    include_assertions: bool = True
    include_negative_cases: bool = False
    max_steps_per_script: int = Field(default=20, ge=5, le=100)


class GenerationJobRequest(BaseModel):
    requirement_ids: list[uuid.UUID] = Field(min_length=1)
    output_formats: list[ScriptFormat] = [ScriptFormat.PLAYWRIGHT_TS, ScriptFormat.GHERKIN]
    generation_config: GenerationConfig = GenerationConfig()


class CrawlAuthConfig(BaseModel):
    type: CrawlAuthType = CrawlAuthType.FORM
    credentials_key_vault_ref: str | None = None


class CrawlJobRequest(BaseModel):
    crawler_type: CrawlerType = CrawlerType.WEB
    target_url: str | None = None          # Web crawl
    launchpad_url: str | None = None       # SAP Fiori crawl
    auth_config: CrawlAuthConfig = CrawlAuthConfig()
    max_pages: int = Field(default=100, ge=1, le=1000)
    max_depth: int = Field(default=5, ge=1, le=20)
    exclude_patterns: list[str] = []
    same_origin_only: bool = True
    generate_scripts: bool = True
    tile_groups: list[str] = []            # SAP Fiori: restrict to specific tile groups
