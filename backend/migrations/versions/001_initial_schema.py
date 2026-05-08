"""Initial schema — all KAATS tables.

Revision ID: 001_initial_schema
Revises: (none)
Create Date: 2026-05-07

Creates:
  global_config
  enterprises
  companies
  business_domains
  users
  user_roles
  projects
  environments
  requirements
  test_scripts
  test_script_versions
  jobs
  crawl_jobs
  crawl_pages
  test_cycles
  test_assignments
  test_results
  execution_evidence
  defects
  audit_logs

Then installs Azure SQL Row-Level Security on all company-scoped tables.
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mssql

revision: str = "001_initial_schema"
down_revision: str | None = None
branch_labels: tuple | None = None
depends_on: str | None = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _uuid_col(name: str, **kw) -> sa.Column:
    return sa.Column(name, mssql.UNIQUEIDENTIFIER, **kw)


def _ts_col(name: str, nullable: bool = False) -> sa.Column:
    return sa.Column(
        name,
        sa.DateTime(timezone=True),
        nullable=nullable,
        server_default=sa.text("SYSDATETIMEOFFSET()"),
    )


# ---------------------------------------------------------------------------
# Upgrade
# ---------------------------------------------------------------------------


def upgrade() -> None:
    # ------------------------------------------------------------------
    # global_config
    # ------------------------------------------------------------------
    op.create_table(
        "global_config",
        _uuid_col("id", primary_key=True),
        sa.Column("key", sa.String(255), nullable=False),
        sa.Column("value", sa.Text, nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("is_secret", sa.Boolean, nullable=False, server_default="0"),
        _ts_col("created_at"),
        _ts_col("updated_at"),
    )
    op.create_index("ix_global_config_key", "global_config", ["key"], unique=True)

    # ------------------------------------------------------------------
    # enterprises
    # ------------------------------------------------------------------
    op.create_table(
        "enterprises",
        _uuid_col("id", primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("slug", sa.String(100), nullable=False),
        sa.Column("azure_ad_tenant_id", sa.String(255), nullable=True),
        sa.Column("settings", mssql.JSON, nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="1"),
        _ts_col("created_at"),
        _ts_col("updated_at"),
    )
    op.create_index("ix_enterprises_slug", "enterprises", ["slug"], unique=True)
    op.create_index(
        "ix_enterprises_azure_ad_tenant_id",
        "enterprises",
        ["azure_ad_tenant_id"],
        unique=True,
    )

    # ------------------------------------------------------------------
    # companies
    # ------------------------------------------------------------------
    op.create_table(
        "companies",
        _uuid_col("id", primary_key=True),
        _uuid_col(
            "enterprise_id",
            sa.ForeignKey("enterprises.id"),
            nullable=False,
        ),
        _uuid_col("tenant_id", nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("slug", sa.String(100), nullable=False),
        sa.Column("settings", mssql.JSON, nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="1"),
        _ts_col("created_at"),
        _ts_col("updated_at"),
        sa.UniqueConstraint("enterprise_id", "slug", name="uq_companies_enterprise_slug"),
        sa.UniqueConstraint("tenant_id", name="uq_companies_tenant_id"),
    )
    op.create_index("ix_companies_enterprise_id", "companies", ["enterprise_id"])
    op.create_index("ix_companies_tenant_id", "companies", ["tenant_id"])

    # ------------------------------------------------------------------
    # business_domains
    # ------------------------------------------------------------------
    op.create_table(
        "business_domains",
        _uuid_col("id", primary_key=True),
        _uuid_col(
            "tenant_id",
            sa.ForeignKey("companies.tenant_id"),
            nullable=False,
        ),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("code", sa.String(100), nullable=False),
        sa.Column("description", sa.String(1000), nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="1"),
        _ts_col("created_at"),
        _ts_col("updated_at"),
        sa.UniqueConstraint("tenant_id", "code", name="uq_business_domains_tenant_code"),
    )
    op.create_index("ix_business_domains_tenant_id", "business_domains", ["tenant_id"])

    # ------------------------------------------------------------------
    # users
    # ------------------------------------------------------------------
    op.create_table(
        "users",
        _uuid_col("id", primary_key=True),
        sa.Column("azure_oid", sa.String(255), nullable=False),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("display_name", sa.String(255), nullable=False),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="1"),
        sa.Column("is_global_admin", sa.Boolean, nullable=False, server_default="0"),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        _ts_col("created_at"),
        _ts_col("updated_at"),
    )
    op.create_index("ix_users_azure_oid", "users", ["azure_oid"], unique=True)
    op.create_index("ix_users_email", "users", ["email"])

    # ------------------------------------------------------------------
    # user_roles
    # ------------------------------------------------------------------
    op.create_table(
        "user_roles",
        _uuid_col("id", primary_key=True),
        _uuid_col("user_id", sa.ForeignKey("users.id"), nullable=False),
        _uuid_col("tenant_id", nullable=False),
        sa.Column("role", sa.String(10), nullable=False),
        sa.Column("domain_code", sa.String(100), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("SYSDATETIMEOFFSET()")),
        _uuid_col("assigned_by", sa.ForeignKey("users.id"), nullable=True),
        sa.UniqueConstraint(
            "user_id", "tenant_id", "role", "domain_code",
            name="uq_user_roles_user_tenant_role_domain",
        ),
    )
    op.create_index("ix_user_roles_user_id", "user_roles", ["user_id"])
    op.create_index("ix_user_roles_tenant_id", "user_roles", ["tenant_id"])
    op.create_index(
        "ix_user_roles_tenant_created", "user_roles", ["tenant_id", "created_at"]
    )

    # ------------------------------------------------------------------
    # projects
    # ------------------------------------------------------------------
    op.create_table(
        "projects",
        _uuid_col("id", primary_key=True),
        _uuid_col("tenant_id", nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="ACTIVE"),
        sa.Column("system_type", sa.String(20), nullable=False, server_default="WEB"),
        sa.Column("base_url", sa.String(2000), nullable=True),
        sa.Column("settings", mssql.JSON, nullable=True),
        _uuid_col("created_by", sa.ForeignKey("users.id"), nullable=False),
        _ts_col("created_at"),
        _ts_col("updated_at"),
    )
    op.create_index("ix_projects_tenant_id", "projects", ["tenant_id"])
    op.create_index(
        "ix_projects_tenant_created", "projects", ["tenant_id", "created_at"]
    )

    # ------------------------------------------------------------------
    # environments
    # ------------------------------------------------------------------
    op.create_table(
        "environments",
        _uuid_col("id", primary_key=True),
        _uuid_col("tenant_id", nullable=False),
        _uuid_col("project_id", sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("type", sa.String(20), nullable=False, server_default="QA"),
        sa.Column("base_url", sa.String(2000), nullable=True),
        sa.Column("requires_bpo_approval", sa.Boolean, nullable=False, server_default="0"),
        sa.Column("gxp_mode", sa.Boolean, nullable=False, server_default="0"),
        _ts_col("created_at"),
        _ts_col("updated_at"),
    )
    op.create_index("ix_environments_tenant_id", "environments", ["tenant_id"])
    op.create_index("ix_environments_project_id", "environments", ["project_id"])

    # ------------------------------------------------------------------
    # requirements
    # ------------------------------------------------------------------
    op.create_table(
        "requirements",
        _uuid_col("id", primary_key=True),
        _uuid_col("tenant_id", nullable=False),
        _uuid_col("project_id", sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("source_type", sa.String(20), nullable=False, server_default="TEXT"),
        sa.Column("source_ref", sa.String(500), nullable=True),
        sa.Column("content_text", sa.Text, nullable=True),
        sa.Column("blob_uri", sa.String(1000), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="PENDING"),
        sa.Column("business_domain", sa.String(100), nullable=True),
        sa.Column("priority", sa.String(20), nullable=False, server_default="MEDIUM"),
        sa.Column("tags", mssql.JSON, nullable=True),
        _uuid_col("uploaded_by", sa.ForeignKey("users.id"), nullable=False),
        _ts_col("created_at"),
        _ts_col("updated_at"),
    )
    op.create_index("ix_requirements_tenant_id", "requirements", ["tenant_id"])
    op.create_index("ix_requirements_project_id", "requirements", ["project_id"])
    op.create_index("ix_requirements_business_domain", "requirements", ["business_domain"])
    op.create_index(
        "ix_requirements_tenant_created", "requirements", ["tenant_id", "created_at"]
    )

    # ------------------------------------------------------------------
    # test_scripts
    # ------------------------------------------------------------------
    op.create_table(
        "test_scripts",
        _uuid_col("id", primary_key=True),
        _uuid_col("tenant_id", nullable=False),
        _uuid_col("requirement_id", sa.ForeignKey("requirements.id"), nullable=False),
        _uuid_col("project_id", sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("format", sa.String(30), nullable=False, server_default="playwright_ts"),
        sa.Column("status", sa.String(20), nullable=False, server_default="DRAFT"),
        sa.Column("cosmos_doc_id", sa.String(500), nullable=True),
        sa.Column("current_version", sa.Integer, nullable=False, server_default="1"),
        sa.Column("is_ai_generated", sa.Boolean, nullable=False, server_default="1"),
        _uuid_col("approved_by", sa.ForeignKey("users.id"), nullable=True),
        _uuid_col("created_by", sa.ForeignKey("users.id"), nullable=False),
        _ts_col("created_at"),
        _ts_col("updated_at"),
    )
    op.create_index("ix_test_scripts_tenant_id", "test_scripts", ["tenant_id"])
    op.create_index("ix_test_scripts_requirement_id", "test_scripts", ["requirement_id"])
    op.create_index("ix_test_scripts_project_id", "test_scripts", ["project_id"])
    op.create_index("ix_test_scripts_status", "test_scripts", ["status"])
    op.create_index(
        "ix_test_scripts_tenant_created", "test_scripts", ["tenant_id", "created_at"]
    )

    # ------------------------------------------------------------------
    # test_script_versions
    # ------------------------------------------------------------------
    op.create_table(
        "test_script_versions",
        _uuid_col("id", primary_key=True),
        _uuid_col("tenant_id", nullable=False),
        _uuid_col("script_id", sa.ForeignKey("test_scripts.id"), nullable=False),
        sa.Column("version_number", sa.Integer, nullable=False),
        sa.Column("cosmos_doc_id", sa.String(500), nullable=False),
        sa.Column("change_summary", sa.Text, nullable=True),
        sa.Column("is_ai_generated", sa.Boolean, nullable=False, server_default="1"),
        _uuid_col("created_by", sa.ForeignKey("users.id"), nullable=False),
        _ts_col("created_at"),
        _ts_col("updated_at"),
    )
    op.create_index("ix_test_script_versions_tenant_id", "test_script_versions", ["tenant_id"])
    op.create_index("ix_test_script_versions_script_id", "test_script_versions", ["script_id"])
    op.create_index(
        "ix_test_script_versions_tenant_created",
        "test_script_versions",
        ["tenant_id", "created_at"],
    )

    # ------------------------------------------------------------------
    # jobs  (AI generation, export, report)
    # ------------------------------------------------------------------
    op.create_table(
        "jobs",
        _uuid_col("id", primary_key=True),
        _uuid_col("tenant_id", nullable=False),
        _uuid_col("project_id", sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("job_type", sa.String(20), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="PENDING"),
        _uuid_col("created_by", sa.ForeignKey("users.id"), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("input_payload", sa.Text, nullable=True),
        sa.Column("cosmos_result_id", sa.String(500), nullable=True),
        _ts_col("created_at"),
        _ts_col("updated_at"),
    )
    op.create_index("ix_jobs_tenant_id", "jobs", ["tenant_id"])
    op.create_index("ix_jobs_project_id", "jobs", ["project_id"])
    op.create_index("ix_jobs_status", "jobs", ["status"])
    op.create_index("ix_jobs_tenant_created", "jobs", ["tenant_id", "created_at"])

    # ------------------------------------------------------------------
    # crawl_jobs
    # ------------------------------------------------------------------
    op.create_table(
        "crawl_jobs",
        _uuid_col("id", primary_key=True),
        _uuid_col("tenant_id", nullable=False),
        _uuid_col("project_id", sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("crawler_type", sa.String(20), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="PENDING"),
        sa.Column("target_url", sa.String(2000), nullable=True),
        sa.Column("launchpad_url", sa.String(2000), nullable=True),
        sa.Column("max_pages", sa.Integer, nullable=False, server_default="50"),
        sa.Column("auth_type", sa.String(20), nullable=False, server_default="none"),
        sa.Column("auth_config", sa.Text, nullable=True),
        sa.Column("generate_scripts", sa.Boolean, nullable=False, server_default="1"),
        _uuid_col("created_by", sa.ForeignKey("users.id"), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("pages_found", sa.Integer, nullable=True),
        sa.Column("scripts_generated", sa.Integer, nullable=True),
        sa.Column("error_message", sa.Text, nullable=True),
        _ts_col("created_at"),
        _ts_col("updated_at"),
    )
    op.create_index("ix_crawl_jobs_tenant_id", "crawl_jobs", ["tenant_id"])
    op.create_index("ix_crawl_jobs_project_id", "crawl_jobs", ["project_id"])
    op.create_index("ix_crawl_jobs_status", "crawl_jobs", ["status"])
    op.create_index("ix_crawl_jobs_tenant_created", "crawl_jobs", ["tenant_id", "created_at"])

    # ------------------------------------------------------------------
    # crawl_pages
    # ------------------------------------------------------------------
    op.create_table(
        "crawl_pages",
        _uuid_col("id", primary_key=True),
        _uuid_col("tenant_id", nullable=False),
        _uuid_col("crawl_job_id", sa.ForeignKey("crawl_jobs.id"), nullable=False),
        sa.Column("url", sa.String(2000), nullable=False),
        sa.Column("title", sa.String(500), nullable=True),
        sa.Column("page_hash", sa.String(64), nullable=True),
        sa.Column("depth", sa.Integer, nullable=False, server_default="0"),
        sa.Column("elements_json", sa.Text, nullable=True),
        sa.Column("screenshot_uri", sa.String(1000), nullable=True),
        _uuid_col("generated_script_id", sa.ForeignKey("test_scripts.id"), nullable=True),
        _ts_col("created_at"),
        _ts_col("updated_at"),
    )
    op.create_index("ix_crawl_pages_tenant_id", "crawl_pages", ["tenant_id"])
    op.create_index("ix_crawl_pages_crawl_job_id", "crawl_pages", ["crawl_job_id"])
    op.create_index("ix_crawl_pages_page_hash", "crawl_pages", ["page_hash"])
    op.create_index(
        "ix_crawl_pages_tenant_created", "crawl_pages", ["tenant_id", "created_at"]
    )

    # ------------------------------------------------------------------
    # test_cycles
    # ------------------------------------------------------------------
    op.create_table(
        "test_cycles",
        _uuid_col("id", primary_key=True),
        _uuid_col("tenant_id", nullable=False),
        _uuid_col("project_id", sa.ForeignKey("projects.id"), nullable=False),
        _uuid_col("environment_id", sa.ForeignKey("environments.id"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="DRAFT"),
        _uuid_col("created_by", sa.ForeignKey("users.id"), nullable=False),
        _uuid_col("lead_user_id", sa.ForeignKey("users.id"), nullable=True),
        sa.Column("planned_start_date", sa.Date, nullable=True),
        sa.Column("planned_end_date", sa.Date, nullable=True),
        sa.Column("actual_start_date", sa.Date, nullable=True),
        sa.Column("actual_end_date", sa.Date, nullable=True),
        _uuid_col("bpo_approved_by", sa.ForeignKey("users.id"), nullable=True),
        sa.Column("bpo_approved_at", sa.DateTime(timezone=True), nullable=True),
        _ts_col("created_at"),
        _ts_col("updated_at"),
    )
    op.create_index("ix_test_cycles_tenant_id", "test_cycles", ["tenant_id"])
    op.create_index("ix_test_cycles_project_id", "test_cycles", ["project_id"])
    op.create_index(
        "ix_test_cycles_tenant_created", "test_cycles", ["tenant_id", "created_at"]
    )

    # ------------------------------------------------------------------
    # test_assignments
    # ------------------------------------------------------------------
    op.create_table(
        "test_assignments",
        _uuid_col("id", primary_key=True),
        _uuid_col("tenant_id", nullable=False),
        _uuid_col("cycle_id", sa.ForeignKey("test_cycles.id"), nullable=False),
        _uuid_col("script_id", sa.ForeignKey("test_scripts.id"), nullable=False),
        sa.Column("script_version", sa.Integer, nullable=False, server_default="1"),
        _uuid_col("assigned_to", sa.ForeignKey("users.id"), nullable=False),
        _uuid_col("assigned_by", sa.ForeignKey("users.id"), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="NOT_STARTED"),
        sa.Column("due_date", sa.Date, nullable=True),
        sa.Column("notes", sa.Text, nullable=True),
        _ts_col("created_at"),
        _ts_col("updated_at"),
    )
    op.create_index("ix_test_assignments_tenant_id", "test_assignments", ["tenant_id"])
    op.create_index("ix_test_assignments_cycle_id", "test_assignments", ["cycle_id"])
    op.create_index("ix_test_assignments_script_id", "test_assignments", ["script_id"])
    op.create_index("ix_test_assignments_status", "test_assignments", ["status"])
    op.create_index(
        "ix_test_assignments_tenant_created",
        "test_assignments",
        ["tenant_id", "created_at"],
    )

    # ------------------------------------------------------------------
    # test_results
    # ------------------------------------------------------------------
    op.create_table(
        "test_results",
        _uuid_col("id", primary_key=True),
        _uuid_col("tenant_id", nullable=False),
        _uuid_col(
            "assignment_id",
            sa.ForeignKey("test_assignments.id"),
            nullable=False,
        ),
        sa.Column("status", sa.String(20), nullable=False),
        _uuid_col("executed_by", sa.ForeignKey("users.id"), nullable=False),
        sa.Column("executed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("duration_seconds", sa.Integer, nullable=True),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("step_results", sa.Text, nullable=True),
        _ts_col("created_at"),
        _ts_col("updated_at"),
        sa.UniqueConstraint("assignment_id", name="uq_test_results_assignment_id"),
    )
    op.create_index("ix_test_results_tenant_id", "test_results", ["tenant_id"])
    op.create_index("ix_test_results_assignment_id", "test_results", ["assignment_id"])
    op.create_index("ix_test_results_status", "test_results", ["status"])
    op.create_index(
        "ix_test_results_tenant_created", "test_results", ["tenant_id", "created_at"]
    )

    # ------------------------------------------------------------------
    # execution_evidence
    # ------------------------------------------------------------------
    op.create_table(
        "execution_evidence",
        _uuid_col("id", primary_key=True),
        _uuid_col("tenant_id", nullable=False),
        _uuid_col("result_id", sa.ForeignKey("test_results.id"), nullable=False),
        sa.Column("blob_uri", sa.String(1000), nullable=False),
        sa.Column("file_name", sa.String(500), nullable=False),
        sa.Column("content_type", sa.String(200), nullable=True),
        _uuid_col("uploaded_by", sa.ForeignKey("users.id"), nullable=False),
        sa.Column("uploaded_at", sa.DateTime(timezone=True), nullable=False),
        _ts_col("created_at"),
        _ts_col("updated_at"),
    )
    op.create_index("ix_execution_evidence_tenant_id", "execution_evidence", ["tenant_id"])
    op.create_index("ix_execution_evidence_result_id", "execution_evidence", ["result_id"])

    # ------------------------------------------------------------------
    # defects
    # ------------------------------------------------------------------
    op.create_table(
        "defects",
        _uuid_col("id", primary_key=True),
        _uuid_col("tenant_id", nullable=False),
        _uuid_col("test_result_id", sa.ForeignKey("test_results.id"), nullable=False),
        _uuid_col("project_id", sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("severity", sa.String(20), nullable=False, server_default="MEDIUM"),
        sa.Column("status", sa.String(20), nullable=False, server_default="OPEN"),
        sa.Column("external_ref", sa.String(500), nullable=True),
        _uuid_col("created_by", sa.ForeignKey("users.id"), nullable=False),
        _ts_col("created_at"),
        _ts_col("updated_at"),
    )
    op.create_index("ix_defects_tenant_id", "defects", ["tenant_id"])
    op.create_index("ix_defects_test_result_id", "defects", ["test_result_id"])
    op.create_index("ix_defects_project_id", "defects", ["project_id"])
    op.create_index("ix_defects_tenant_created", "defects", ["tenant_id", "created_at"])

    # ------------------------------------------------------------------
    # audit_logs  (append-only — no updated_at)
    # ------------------------------------------------------------------
    op.create_table(
        "audit_logs",
        _uuid_col("id", primary_key=True),
        _uuid_col("tenant_id", nullable=False),
        _uuid_col("user_id", sa.ForeignKey("users.id"), nullable=False),
        sa.Column("action", sa.String(100), nullable=False),
        sa.Column("resource_type", sa.String(100), nullable=False),
        sa.Column("resource_id", sa.String(500), nullable=False),
        sa.Column("before_state", sa.Text, nullable=True),
        sa.Column("after_state", sa.Text, nullable=True),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("SYSDATETIMEOFFSET()"),
        ),
    )
    op.create_index("ix_audit_logs_tenant_id", "audit_logs", ["tenant_id"])
    op.create_index(
        "ix_audit_logs_tenant_created", "audit_logs", ["tenant_id", "created_at"]
    )
    op.create_index(
        "ix_audit_logs_resource",
        "audit_logs",
        ["tenant_id", "resource_type", "resource_id"],
    )

    # ------------------------------------------------------------------
    # Row-Level Security
    # ------------------------------------------------------------------
    # Create a schema-bound inline table-valued function that returns 1
    # when the row's tenant_id matches SESSION_CONTEXT(N'tenant_id').
    # The function is used by FILTER and BLOCK predicates on every
    # company-scoped table.
    #
    # NOTE: Global admin connections set SESSION_CONTEXT to NULL, which
    # bypasses the predicates (CAST(NULL AS UNIQUEIDENTIFIER) IS NULL).
    # All other connections MUST set session context before querying.
    op.execute(
        """
        CREATE FUNCTION dbo.fn_rls_tenant_predicate(@tenant_id UNIQUEIDENTIFIER)
        RETURNS TABLE
        WITH SCHEMABINDING
        AS
        RETURN
            SELECT 1 AS result
            WHERE
                SESSION_CONTEXT(N'tenant_id') IS NULL
                OR @tenant_id = CAST(SESSION_CONTEXT(N'tenant_id') AS UNIQUEIDENTIFIER)
        """
    )

    _rls_tables = [
        "user_roles",
        "projects",
        "environments",
        "requirements",
        "test_scripts",
        "test_script_versions",
        "jobs",
        "crawl_jobs",
        "crawl_pages",
        "test_cycles",
        "test_assignments",
        "test_results",
        "execution_evidence",
        "defects",
        "audit_logs",
        "business_domains",
    ]

    for table in _rls_tables:
        policy_name = f"rls_policy_{table}"
        op.execute(
            f"""
            CREATE SECURITY POLICY dbo.{policy_name}
            ADD FILTER PREDICATE dbo.fn_rls_tenant_predicate(tenant_id) ON dbo.{table},
            ADD BLOCK  PREDICATE dbo.fn_rls_tenant_predicate(tenant_id) ON dbo.{table} AFTER INSERT
            WITH (STATE = ON)
            """
        )


# ---------------------------------------------------------------------------
# Downgrade
# ---------------------------------------------------------------------------


def downgrade() -> None:
    _rls_tables = [
        "user_roles", "projects", "environments", "requirements",
        "test_scripts", "test_script_versions", "jobs", "crawl_jobs",
        "crawl_pages", "test_cycles", "test_assignments", "test_results",
        "execution_evidence", "defects", "audit_logs", "business_domains",
    ]
    for table in _rls_tables:
        op.execute(f"DROP SECURITY POLICY IF EXISTS dbo.rls_policy_{table}")

    op.execute("DROP FUNCTION IF EXISTS dbo.fn_rls_tenant_predicate")

    for tbl in [
        "audit_logs", "defects", "execution_evidence", "test_results",
        "test_assignments", "test_cycles", "crawl_pages", "crawl_jobs",
        "jobs", "test_script_versions", "test_scripts", "requirements",
        "environments", "projects", "user_roles", "users",
        "business_domains", "companies", "enterprises", "global_config",
    ]:
        op.drop_table(tbl)
