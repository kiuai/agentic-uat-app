"""
Azure Cosmos DB document schemas for the test_artifacts container.

This module is documentation-only — no runtime code. It defines the TypedDict
shapes for documents stored in the per-tenant Cosmos containers
(kaats-{tenant_id}).

Container configuration
-----------------------
  Account:        KAATS Cosmos DB account (serverless or provisioned)
  Database:       kaats-db
  Container:      kaats-{tenant_id}      (one per company/tenant)
  Partition key:  /project_id
  Default TTL:    -1 (disabled; TTL set per-document for AI logs only)
  Indexing:       Automatic on all string/number paths
  Conflict res.:  Last-Write-Wins

Document types
--------------
  test_script     — generated or manually authored script body + metadata
  ai_log          — raw LLM prompt/response pairs (TTL: 30 days)
  crawl_snapshot  — full crawl run DOM snapshot + element inventory

All documents include a 'type' discriminator field.
"""

from __future__ import annotations

from typing import Any, Literal, TypedDict


# ---------------------------------------------------------------------------
# Shared base
# ---------------------------------------------------------------------------


class _CosmosDocBase(TypedDict):
    """Fields present on every document."""

    id: str                  # UUID string — Cosmos document id
    type: str                # Discriminator: "test_script" | "ai_log" | "crawl_snapshot"
    tenant_id: str           # company.id — mirrors SQL tenant for cross-store joins
    project_id: str          # Partition key — UUID string
    created_at: str          # ISO-8601 UTC datetime
    updated_at: str          # ISO-8601 UTC datetime
    created_by: str          # user.id UUID string
    _ts: int                 # Cosmos server-side unix timestamp (read-only)


# ---------------------------------------------------------------------------
# test_script document
# ---------------------------------------------------------------------------


class TestScriptStep(TypedDict):
    step_number: int
    description: str
    action: str                      # e.g. "click", "fill", "assert_text"
    selector: str | None             # CSS or XPath selector
    value: str | None                # Input value or expected text
    screenshot_hint: str | None


class TestScriptCosmosDoc(_CosmosDocBase):
    """
    Full content of a test script version.

    The SQL test_scripts row holds metadata (status, approval) and links to
    this document via cosmos_doc_id. The SQL test_script_versions rows each
    link to a separate Cosmos document for historical version content.
    """

    type: Literal["test_script"]

    # SQL foreign key back-references
    sql_script_id: str               # test_scripts.id UUID string
    version_number: int

    title: str
    description: str | None

    # Structured steps (AI-generated or manually entered)
    steps: list[TestScriptStep]

    # Rendered script bodies keyed by ScriptFormat enum value
    rendered_scripts: dict[str, str]  # {"playwright_ts": "...", "gherkin": "..."}

    # Source metadata
    requirement_ids: list[str]
    is_ai_generated: bool
    ai_model: str | None             # e.g. "gpt-4o"
    generation_job_id: str | None    # jobs.id UUID string

    # Approval metadata (denormalised from SQL for read performance)
    status: str                      # ScriptStatus enum value
    approved_by: str | None
    approved_at: str | None

    tags: list[str]
    domain_code: str | None


# ---------------------------------------------------------------------------
# ai_log document
# ---------------------------------------------------------------------------


class AILogEntry(TypedDict):
    stage: str               # "decompose" | "generate_steps" | "format" | "validate"
    prompt: str
    response: str
    input_tokens: int
    output_tokens: int
    latency_ms: int


class AILogCosmosDoc(_CosmosDocBase):
    """
    Raw LLM interaction log for a single AI generation run.

    TTL is set to 2_592_000 (30 days) on creation so logs auto-expire.
    Never expose these documents to end-users — they may contain PII from
    requirement text.
    """

    type: Literal["ai_log"]
    ttl: int                        # 2_592_000 (30 days in seconds)

    job_id: str                     # jobs.id UUID string
    requirement_ids: list[str]
    model: str
    total_input_tokens: int
    total_output_tokens: int
    total_latency_ms: int
    entries: list[AILogEntry]
    error: str | None


# ---------------------------------------------------------------------------
# crawl_snapshot document
# ---------------------------------------------------------------------------


class CrawlPageSnapshot(TypedDict):
    url: str
    title: str | None
    depth: int
    page_hash: str | None           # SHA-256 of normalised DOM skeleton
    screenshot_uri: str | None      # Azure Blob URI
    elements: list[dict[str, Any]]  # [{selector, tag, text, role, visible}]
    outbound_links: list[str]


class CrawlSnapshotCosmosDoc(_CosmosDocBase):
    """
    Full crawl run snapshot including all discovered pages and element inventory.

    The SQL crawl_pages rows are the queryable index; this document holds the
    full element inventory for AI script generation without bloating SQL.
    """

    type: Literal["crawl_snapshot"]

    crawl_job_id: str               # crawl_jobs.id UUID string
    crawler_type: str               # "WEB" | "SAP_FIORI"
    target_url: str | None
    launchpad_url: str | None
    pages_crawled: int
    pages: list[CrawlPageSnapshot]
    sap_tile_groups: list[str]      # SAP Fiori only: discovered tile group names
    duration_seconds: int
