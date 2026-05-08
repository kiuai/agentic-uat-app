"""init

Revision ID: 0001_init
Revises: 
Create Date: 2025-12-18
"""

from alembic import op
import sqlalchemy as sa

revision = "0001_init"
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    # users / roles
    op.create_table(
        "users",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("user_id", sa.String(64), nullable=False, unique=True, index=True),
        sa.Column("email", sa.String(255), nullable=True),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("is_active", sa.Boolean, server_default=sa.true(), nullable=False),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column("last_login_at", sa.DateTime, nullable=True),
    )
    op.create_table(
        "roles",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("name", sa.Enum("validation_tester","validation_lead","qa","admin", name="rolename"), nullable=False, unique=True),
    )
    op.create_table(
        "user_roles",
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id"), primary_key=True),
        sa.Column("role_id", sa.Integer, sa.ForeignKey("roles.id"), primary_key=True),
    )

    op.create_table(
        "projects",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("name", sa.String(200), nullable=False, unique=True),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False),
    )

    op.create_table(
        "applications",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("project_id", sa.Integer, sa.ForeignKey("projects.id"), nullable=False, index=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("base_url", sa.String(500), nullable=False),
        sa.Column("environment", sa.String(100), nullable=False),
        sa.Column("created_at", sa.DateTime, nullable=False),
    )

    op.create_table(
        "requirements",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("project_id", sa.Integer, sa.ForeignKey("projects.id"), nullable=False, index=True),
        sa.Column("req_id", sa.String(80), nullable=False),
        sa.Column("text", sa.Text, nullable=False),
        sa.Column("priority", sa.String(50), nullable=True),
        sa.Column("risk", sa.String(50), nullable=True),
        sa.Column("source", sa.String(200), nullable=True),
        sa.Column("version", sa.Integer, nullable=False, server_default="1"),
        sa.Column("status", sa.String(30), nullable=False, server_default="Active"),
        sa.UniqueConstraint("project_id","req_id","version", name="uq_req_version"),
    )

    op.create_table(
        "test_bundles",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("project_id", sa.Integer, sa.ForeignKey("projects.id"), nullable=False, index=True),
        sa.Column("version_hash", sa.String(64), nullable=False, index=True),
        sa.Column("status", sa.Enum("draft","approved","rejected", name="testbundlestatus"), nullable=False),
        sa.Column("created_by", sa.Integer, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime, nullable=False),
    )

    op.create_table(
        "tests",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("bundle_id", sa.Integer, sa.ForeignKey("test_bundles.id"), nullable=False, index=True),
        sa.Column("test_id", sa.String(80), nullable=False, index=True),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("objective", sa.Text, nullable=False),
        sa.Column("preconditions", sa.Text, nullable=False),
        sa.Column("data_json", sa.Text, nullable=False),
        sa.Column("risk", sa.String(50), nullable=True),
        sa.Column("requirement_ids_json", sa.Text, nullable=False),
    )

    op.create_table(
        "test_steps",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("test_case_id", sa.Integer, sa.ForeignKey("tests.id"), nullable=False, index=True),
        sa.Column("step_index", sa.Integer, nullable=False),
        sa.Column("action", sa.String(40), nullable=False),
        sa.Column("selector_json", sa.Text, nullable=True),
        sa.Column("input", sa.Text, nullable=True),
        sa.Column("expected", sa.Text, nullable=True),
        sa.Column("critical", sa.Boolean, nullable=False, server_default=sa.false()),
    )

    op.create_table(
        "runs",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("bundle_id", sa.Integer, sa.ForeignKey("test_bundles.id"), nullable=False, index=True),
        sa.Column("started_by", sa.Integer, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("started_at", sa.DateTime, nullable=False),
        sa.Column("finished_at", sa.DateTime, nullable=True),
        sa.Column("status", sa.Enum("running","passed","failed","error", name="runstatus"), nullable=False),
        sa.Column("environment_snapshot_json", sa.Text, nullable=False),
    )

    op.create_table(
        "results",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("run_id", sa.Integer, sa.ForeignKey("runs.id"), nullable=False, index=True),
        sa.Column("test_case_id", sa.Integer, sa.ForeignKey("tests.id"), nullable=False, index=True),
        sa.Column("step_id", sa.Integer, sa.ForeignKey("test_steps.id"), nullable=False, index=True),
        sa.Column("status", sa.Enum("pass_","fail", name="resultstatus"), nullable=False),
        sa.Column("message", sa.Text, nullable=True),
        sa.Column("page_url", sa.String(500), nullable=True),
        sa.Column("ts", sa.DateTime, nullable=False),
    )

    op.create_table(
        "evidence",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("result_id", sa.Integer, sa.ForeignKey("results.id"), nullable=False, index=True),
        sa.Column("kind", sa.String(30), nullable=False),
        sa.Column("path", sa.String(800), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime, nullable=False),
    )

    op.create_table(
        "approvals",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("object_type", sa.String(50), nullable=False),
        sa.Column("object_id", sa.Integer, nullable=False, index=True),
        sa.Column("action", sa.String(50), nullable=False),
        sa.Column("status", sa.Enum("approved","rejected", name="approvalstatus"), nullable=False),
        sa.Column("signed_by", sa.Integer, sa.ForeignKey("users.id"), nullable=False, index=True),
        sa.Column("signed_at", sa.DateTime, nullable=False),
        sa.Column("reason", sa.Text, nullable=True),
        sa.Column("signature_hash", sa.String(64), nullable=False),
    )

    op.create_table(
        "audit_log",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("actor_user_id", sa.Integer, sa.ForeignKey("users.id"), nullable=True),
        sa.Column("action", sa.String(100), nullable=False),
        sa.Column("payload_json", sa.Text, nullable=False),
        sa.Column("ts", sa.DateTime, nullable=False),
    )

def downgrade():
    op.drop_table("audit_log")
    op.drop_table("approvals")
    op.drop_table("evidence")
    op.drop_table("results")
    op.drop_table("runs")
    op.drop_table("test_steps")
    op.drop_table("tests")
    op.drop_table("test_bundles")
    op.drop_table("requirements")
    op.drop_table("applications")
    op.drop_table("projects")
    op.drop_table("user_roles")
    op.drop_table("roles")
    op.drop_table("users")
    op.execute("DROP TYPE IF EXISTS rolename")
    op.execute("DROP TYPE IF EXISTS testbundlestatus")
    op.execute("DROP TYPE IF EXISTS runstatus")
    op.execute("DROP TYPE IF EXISTS resultstatus")
    op.execute("DROP TYPE IF EXISTS approvalstatus")
