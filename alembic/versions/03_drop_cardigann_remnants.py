"""drop_cardigann_remnants

Revision ID: 03_drop_cardigann_remnants
Revises: 02_recreate_rules
Create Date: 2026-04-23

"""
from alembic import op
import sqlalchemy as sa

revision = '03_drop_cardigann_remnants'
down_revision = '02_recreate_rules'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_column('arss_feeds', 'indexer_id')
    op.execute("DROP TABLE IF EXISTS arss_filter_rules")


def downgrade() -> None:
    op.add_column('arss_feeds', sa.Column('indexer_id', sa.String(100), nullable=True))
