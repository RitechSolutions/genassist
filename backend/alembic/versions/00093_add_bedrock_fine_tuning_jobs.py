"""add bedrock fine tuning jobs

Revision ID: 21f612ab93ba
Revises: c09bc3d15d9b
Create Date: 2026-07-09 13:57:32.231705

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '21f612ab93ba'
down_revision: Union[str, None] = 'c09bc3d15d9b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'bedrock_fine_tuning_jobs',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('job_arn', sa.String(), nullable=False),
        sa.Column('job_name', sa.String(), nullable=False),
        sa.Column('base_model_id', sa.String(), nullable=False),
        sa.Column('custom_model_name', sa.String(), nullable=False),
        sa.Column('suffix', sa.String(length=40), nullable=True),
        sa.Column('hyperparameters', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('region', sa.String(), nullable=False),
        sa.Column('training_data_s3_uri', sa.String(), nullable=False),
        sa.Column('validation_data_s3_uri', sa.String(), nullable=True),
        sa.Column('output_s3_uri', sa.String(), nullable=True),
        sa.Column(
            'status',
            sa.Enum('IN_PROGRESS', 'COMPLETED', 'FAILED', 'STOPPING', 'STOPPED', name='bedrockjobstatus'),
            nullable=False,
        ),
        sa.Column('custom_model_arn', sa.String(), nullable=True),
        sa.Column(
            'deployment_status',
            sa.Enum('NOT_DEPLOYED', 'CREATING', 'ACTIVE', 'FAILED', name='bedrockdeploymentstatus'),
            nullable=False,
        ),
        sa.Column('deployment_arn', sa.String(), nullable=True),
        sa.Column('finished_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_synced_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('trained_tokens', sa.Integer(), nullable=True),
        sa.Column('metrics', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('created_by', sa.UUID(), nullable=True),
        sa.Column('updated_by', sa.UUID(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
        sa.Column('is_deleted', sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_bedrock_fine_tuning_jobs_job_arn'), 'bedrock_fine_tuning_jobs', ['job_arn'], unique=True)
    op.create_index(op.f('ix_bedrock_fine_tuning_jobs_status'), 'bedrock_fine_tuning_jobs', ['status'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_bedrock_fine_tuning_jobs_status'), table_name='bedrock_fine_tuning_jobs')
    op.drop_index(op.f('ix_bedrock_fine_tuning_jobs_job_arn'), table_name='bedrock_fine_tuning_jobs')
    op.drop_table('bedrock_fine_tuning_jobs')
    op.execute('DROP TYPE IF EXISTS bedrockjobstatus')
    op.execute('DROP TYPE IF EXISTS bedrockdeploymentstatus')
