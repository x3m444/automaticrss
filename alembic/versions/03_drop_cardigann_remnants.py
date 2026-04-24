"""drop_arss_filter_rules

Revision ID: 03_drop_cardigann_remnants
Revises: 02_recreate_rules
Create Date: 2026-04-24

"""
from alembic import op

revision = '03_drop_cardigann_remnants'
down_revision = '02_recreate_rules'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("DROP TABLE IF EXISTS arss_filter_rules")


def downgrade() -> None:
    pass
