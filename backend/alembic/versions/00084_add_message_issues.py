"""add_message_issues

Revision ID: b7c8d9e0f1a2
Revises: 753019ca4eb2
Create Date: 2026-06-16 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'b7c8d9e0f1a2'
down_revision: Union[str, None] = '753019ca4eb2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'message_issues',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('message_feedback_id', sa.UUID(), nullable=False),
        sa.Column('status', sa.String(length=50), server_default='open', nullable=False),
        sa.Column('resolved_by', sa.UUID(), nullable=True),
        sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_by', sa.UUID(), nullable=True),
        sa.Column('updated_by', sa.UUID(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
        sa.Column('is_deleted', sa.Integer(), server_default=sa.text('0'), nullable=False),
        sa.ForeignKeyConstraint(['message_feedback_id'], ['message_feedback.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('message_feedback_id', name='uq_message_issues_message_feedback_id'),
    )


def downgrade() -> None:
    op.drop_table('message_issues')
