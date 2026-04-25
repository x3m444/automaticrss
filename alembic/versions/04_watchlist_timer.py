"""watchlist_timer_columns

Revision ID: 04_watchlist_timer
Revises: 03_drop_cardigann_remnants
Create Date: 2026-04-25

"""
from alembic import op
import sqlalchemy as sa

revision = '04_watchlist_timer'
down_revision = '03_drop_cardigann_remnants'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('arss_watchlist', sa.Column('check_interval_minutes', sa.Integer(), server_default='120', nullable=True))
    op.add_column('arss_watchlist', sa.Column('last_run_at', sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column('arss_watchlist', 'last_run_at')
    op.drop_column('arss_watchlist', 'check_interval_minutes')
