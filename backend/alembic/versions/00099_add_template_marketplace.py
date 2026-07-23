"""add template marketplace (templates table + feature flag)

Consolidated migration for the Template Marketplace feature: the full
``templates`` table (private + published/community lifecycle + install
tracking) plus a ``feature.templateMarketplace`` feature flag seeded hidden
(``val='false'``) so the feature is off until an admin enables it.

Revision ID: d4b1f2a3c5e6
Revises: e7a4b0c95d61
Create Date: 2026-07-21 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'd4b1f2a3c5e6'
down_revision: Union[str, None] = 'e7a4b0c95d61'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

FEATURE_FLAG_KEY = "feature.templateMarketplace"


def upgrade() -> None:
    op.create_table(
        'templates',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('title', sa.String(length=120), nullable=False),
        sa.Column('description', sa.String(length=500), nullable=True),
        sa.Column('category', sa.String(length=60), nullable=True),
        sa.Column('icon', sa.String(length=60), nullable=True),
        sa.Column('tags', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('node_types', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('graph', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('agent_config', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('is_official', sa.Boolean(), server_default=sa.text('false'), nullable=False),
        sa.Column('install_count', sa.Integer(), server_default='0', nullable=False),
        sa.Column('status', sa.String(length=20), server_default='private', nullable=False),
        sa.Column('source_tenant', sa.String(length=120), nullable=True),
        sa.Column('published_by', sa.UUID(), nullable=True),
        sa.Column('source_template_id', sa.UUID(), nullable=True),
        sa.Column('approved_by', sa.UUID(), nullable=True),
        sa.Column('approved_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('rejection_reason', sa.String(length=500), nullable=True),
        sa.Column('created_by', sa.UUID(), nullable=True),
        sa.Column('updated_by', sa.UUID(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
        sa.Column('is_deleted', sa.Integer(), server_default=sa.text('0'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_templates_status'), 'templates', ['status'], unique=False)
    op.create_index(op.f('ix_templates_source_template_id'), 'templates', ['source_template_id'], unique=False)
    op.create_index(op.f('ix_templates_created_by'), 'templates', ['created_by'], unique=False)

    # Seed the feature flag hidden by default (idempotent on the unique key).
    op.execute(
        f"""
        INSERT INTO feature_flags (id, key, val, description, is_active, is_deleted)
        VALUES (gen_random_uuid(), '{FEATURE_FLAG_KEY}', 'false',
                'Template Marketplace (browse, publish, and install agent templates)', 1, 0)
        ON CONFLICT (key) DO NOTHING
        """
    )


def downgrade() -> None:
    op.execute(f"DELETE FROM feature_flags WHERE key = '{FEATURE_FLAG_KEY}'")
    op.drop_index(op.f('ix_templates_created_by'), table_name='templates')
    op.drop_index(op.f('ix_templates_source_template_id'), table_name='templates')
    op.drop_index(op.f('ix_templates_status'), table_name='templates')
    op.drop_table('templates')
