"""pages and elements

Revision ID: 0002_pages_elements
Revises: 0001_init
Create Date: 2025-12-18
"""

from alembic import op
import sqlalchemy as sa

revision = "0002_pages_elements"
down_revision = "0001_init"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table(
        "pages",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("application_id", sa.Integer, sa.ForeignKey("applications.id"), nullable=False, index=True),
        sa.Column("url", sa.String(800), nullable=False, index=True),
        sa.Column("title", sa.String(400), nullable=True),
        sa.Column("dom_hash", sa.String(64), nullable=False, index=True),
        sa.Column("discovered_at", sa.DateTime, nullable=False),
    )
    op.create_table(
        "elements",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("page_id", sa.Integer, sa.ForeignKey("pages.id"), nullable=False, index=True),
        sa.Column("selector", sa.String(800), nullable=False),
        sa.Column("role", sa.String(80), nullable=True),
        sa.Column("label", sa.String(300), nullable=True),
        sa.Column("type", sa.String(80), nullable=True),
        sa.Column("metadata_json", sa.Text, nullable=False),
        sa.Column("discovered_at", sa.DateTime, nullable=False),
    )

def downgrade():
    op.drop_table("elements")
    op.drop_table("pages")
