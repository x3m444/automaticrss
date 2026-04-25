"""log_level

Revision ID: 06_log_level
Revises: 05_watchlist_logs
Create Date: 2026-04-25

"""
from alembic import op
import sqlalchemy as sa

revision = '06_log_level'
down_revision = '05_watchlist_logs'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('arss_watchlist', sa.Column('log_level', sa.String(20), server_default='full', nullable=True))
    op.drop_column('arss_watchlist', 'log_detail')


def downgrade() -> None:
    op.add_column('arss_watchlist', sa.Column('log_detail', sa.Boolean(), server_default='true', nullable=True))
    op.drop_column('arss_watchlist', 'log_level')
