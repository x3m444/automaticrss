"""add_categories_to_feeds

Revision ID: 010b86d3625f
Revises:
Create Date: 2026-04-23

"""
from alembic import op
import sqlalchemy as sa

revision = '010b86d3625f'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('arss_feeds', sa.Column('categories', sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column('arss_feeds', 'categories')
