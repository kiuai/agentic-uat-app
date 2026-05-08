"""add llm metadata to test bundles

Revision ID: 0004_bundle_llm_metadata
Revises: 0003_llm_settings
Create Date: 2026-02-06
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "0004_bundle_llm_metadata"
down_revision = "0003_llm_settings"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("test_bundles", sa.Column("llm_provider", sa.String(length=40), nullable=True))
    op.add_column("test_bundles", sa.Column("llm_model", sa.String(length=120), nullable=True))


def downgrade() -> None:
    op.drop_column("test_bundles", "llm_model")
    op.drop_column("test_bundles", "llm_provider")
