"""disk_cleanup

Revision ID: 08_disk_cleanup
Revises: 07_instances
Create Date: 2026-04-25

"""
from alembic import op
import sqlalchemy as sa

revision = '08_disk_cleanup'
down_revision = '07_instances'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('arss_instances', sa.Column('disk_cleanup_enabled', sa.Boolean(), server_default='false', nullable=True))
    op.add_column('arss_instances', sa.Column('disk_min_free_gb',     sa.Integer(), server_default='10',    nullable=True))
    op.add_column('arss_instances', sa.Column('disk_target_free_gb',  sa.Integer(), server_default='20',    nullable=True))


def downgrade() -> None:
    op.drop_column('arss_instances', 'disk_target_free_gb')
    op.drop_column('arss_instances', 'disk_min_free_gb')
    op.drop_column('arss_instances', 'disk_cleanup_enabled')
