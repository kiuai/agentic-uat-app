"""llm settings

Revision ID: 0003_llm_settings
Revises: 0002_pages_elements
Create Date: 2025-12-18
"""

from alembic import op
import sqlalchemy as sa

revision = "0003_llm_settings"
down_revision = "0002_pages_elements"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table(
        "llm_settings",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("project_id", sa.Integer, sa.ForeignKey("projects.id"), nullable=False, index=True),
        sa.Column("provider", sa.String(40), nullable=False, server_default="stub"),
        sa.Column("model", sa.String(120), nullable=False, server_default="gpt-5"),
        sa.Column("temperature", sa.Float, nullable=False, server_default="0.2"),
        sa.Column("max_output_tokens", sa.Integer, nullable=False, server_default="2500"),
        sa.Column("strict_json", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("updated_at", sa.DateTime, nullable=False),
    )

def downgrade():
    op.drop_table("llm_settings")
