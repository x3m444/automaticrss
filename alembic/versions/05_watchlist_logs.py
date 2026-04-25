"""watchlist_logs

Revision ID: 05_watchlist_logs
Revises: 04_watchlist_timer
Create Date: 2026-04-25

"""
from alembic import op
import sqlalchemy as sa

revision = '05_watchlist_logs'
down_revision = '04_watchlist_timer'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('arss_watchlist', sa.Column('log_detail', sa.Boolean(), server_default='true', nullable=True))

    op.create_table(
        'arss_wl_logs',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('watchlist_id', sa.Integer(), nullable=True),
        sa.Column('watchlist_name', sa.String(255), nullable=False),
        sa.Column('ran_at', sa.DateTime(), nullable=True),
        sa.Column('items_checked', sa.Integer(), server_default='0'),
        sa.Column('items_sent', sa.Integer(), server_default='0'),
        sa.Column('items_blocked', sa.Integer(), server_default='0'),
        sa.Column('entries', sa.JSON(), nullable=True),
    )


def downgrade() -> None:
    op.drop_table('arss_wl_logs')
    op.drop_column('arss_watchlist', 'log_detail')
