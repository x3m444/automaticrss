"""instances

Revision ID: 07_instances
Revises: 06_log_level
Create Date: 2026-04-25

"""
from alembic import op
import sqlalchemy as sa

revision = '07_instances'
down_revision = '06_log_level'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'arss_instances',
        sa.Column('id',                sa.String(36),  primary_key=True),
        sa.Column('name',              sa.String(255), nullable=False, server_default='Default'),
        sa.Column('transmission_host', sa.String(255), server_default='localhost'),
        sa.Column('transmission_port', sa.Integer(),   server_default='9091'),
        sa.Column('transmission_user', sa.String(255), server_default=''),
        sa.Column('transmission_pass', sa.String(255), server_default=''),
        sa.Column('download_dir',      sa.String(500), nullable=True),
        sa.Column('last_seen_at',      sa.DateTime(),  nullable=True),
        sa.Column('created_at',        sa.DateTime(),  nullable=True),
    )
    op.add_column('arss_downloads', sa.Column('instance_id', sa.String(36), nullable=True))


def downgrade() -> None:
    op.drop_column('arss_downloads', 'instance_id')
    op.drop_table('arss_instances')
