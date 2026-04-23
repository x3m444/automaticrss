"""recreate_arss_rules_with_include_exclude

Revision ID: 02_recreate_rules
Revises: 010b86d3625f
Create Date: 2026-04-23

"""
from alembic import op
import sqlalchemy as sa

revision = '02_recreate_rules'
down_revision = '010b86d3625f'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_table('arss_rules')
    op.create_table(
        'arss_rules',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('feed_ids', sa.JSON(), nullable=True),
        sa.Column('must_contain', sa.JSON(), nullable=True),
        sa.Column('must_not_contain', sa.JSON(), nullable=True),
        sa.Column('size_min_mb', sa.Integer(), nullable=True),
        sa.Column('size_max_gb', sa.Integer(), nullable=True),
        sa.Column('seeders_min', sa.Integer(), nullable=True),
        sa.Column('quality_banned', sa.JSON(), nullable=True),
        sa.Column('resolution_min', sa.String(20), nullable=True),
        sa.Column('languages', sa.JSON(), nullable=True),
        sa.Column('title_blacklist', sa.JSON(), nullable=True),
        sa.Column('download_subdir', sa.String(500), nullable=True),
        sa.Column('is_active', sa.Boolean(), default=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
    )


def downgrade() -> None:
    op.drop_table('arss_rules')
