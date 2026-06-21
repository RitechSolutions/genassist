"""add_workflow_schedule_tables

Revision ID: c8d9e0f1a2b3
Revises: b7c8d9e0f1a2
Create Date: 2026-06-21 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '494257fd515b'
down_revision: Union[str, None] = 'b7c8d9e0f1a2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'workflow_schedules',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('agent_id', sa.UUID(), nullable=False),
        sa.Column('cron_schedule', sa.String(length=100), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('input_data', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('thread_id_mode', sa.String(length=20), nullable=False, server_default='per_run'),
        sa.Column('fixed_thread_id', sa.String(length=255), nullable=True),
        sa.Column('last_run_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_by', sa.UUID(), nullable=True),
        sa.Column('updated_by', sa.UUID(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
        sa.Column('is_deleted', sa.Integer(), server_default=sa.text('0'), nullable=False),
        sa.ForeignKeyConstraint(['agent_id'], ['agents.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('idx_workflow_schedules_agent_id', 'workflow_schedules', ['agent_id'])
    op.create_index('idx_workflow_schedules_is_active', 'workflow_schedules', ['is_active'])

    run_status_enum = postgresql.ENUM(
        'PENDING', 'RUNNING', 'COMPLETED', 'FAILED', 'CANCELLED',
        name='workflow_schedule_run_status_enum',
        create_type=False,
    )
    run_status_enum.create(op.get_bind(), checkfirst=True)

    op.create_table(
        'workflow_schedule_runs',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('schedule_id', sa.UUID(), nullable=False),
        sa.Column('agent_id', sa.UUID(), nullable=False),
        sa.Column('workflow_id', sa.UUID(), nullable=True),
        sa.Column('thread_id', sa.String(length=255), nullable=True),
        sa.Column('status', run_status_enum, nullable=False, server_default='PENDING'),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('execution_output', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('execution_id', sa.UUID(), nullable=True),
        sa.Column('created_by', sa.UUID(), nullable=True),
        sa.Column('updated_by', sa.UUID(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
        sa.Column('is_deleted', sa.Integer(), server_default=sa.text('0'), nullable=False),
        sa.ForeignKeyConstraint(['schedule_id'], ['workflow_schedules.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('idx_workflow_schedule_runs_schedule_id', 'workflow_schedule_runs', ['schedule_id'])
    op.create_index('idx_workflow_schedule_runs_status', 'workflow_schedule_runs', ['status'])
    op.create_index('idx_workflow_schedule_runs_created_at', 'workflow_schedule_runs', ['created_at'])


def downgrade() -> None:
    op.drop_index('idx_workflow_schedule_runs_created_at', table_name='workflow_schedule_runs')
    op.drop_index('idx_workflow_schedule_runs_status', table_name='workflow_schedule_runs')
    op.drop_index('idx_workflow_schedule_runs_schedule_id', table_name='workflow_schedule_runs')
    op.drop_table('workflow_schedule_runs')

    postgresql.ENUM(name='workflow_schedule_run_status_enum').drop(op.get_bind(), checkfirst=True)

    op.drop_index('idx_workflow_schedules_is_active', table_name='workflow_schedules')
    op.drop_index('idx_workflow_schedules_agent_id', table_name='workflow_schedules')
    op.drop_table('workflow_schedules')