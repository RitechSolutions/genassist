"""notification preferences update

Revision ID: 796abc886377
Revises: g7d8e9f0a1b2
Create Date: 2026-05-06 12:17:11.656100

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '796abc886377'
down_revision: Union[str, None] = 'g7d8e9f0a1b2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'notification_types',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('type', sa.String(length=100), nullable=False),
        sa.Column('is_tenant', sa.Boolean(), nullable=False),
        sa.Column('is_enabled', sa.Boolean(), nullable=False),
        sa.Column('created_by', sa.UUID(), nullable=True),
        sa.Column('updated_by', sa.UUID(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
        sa.Column('is_deleted', sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_notification_types_type'), 'notification_types', ['type'], unique=True)

    op.create_table(
        'user_notification_preferences',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('notification_type_id', sa.UUID(), nullable=False),
        sa.Column('is_enabled', sa.Boolean(), nullable=False),
        sa.Column('created_by', sa.UUID(), nullable=True),
        sa.Column('updated_by', sa.UUID(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
        sa.Column('is_deleted', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['notification_type_id'], ['notification_types.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'notification_type_id', name='uq_user_notification_preferences_user_type')
    )
    op.create_index(op.f('ix_user_notification_preferences_notification_type_id'), 'user_notification_preferences', ['notification_type_id'], unique=False)
    op.create_index(op.f('ix_user_notification_preferences_user_id'), 'user_notification_preferences', ['user_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_user_notification_preferences_user_id'), table_name='user_notification_preferences')
    op.drop_index(op.f('ix_user_notification_preferences_notification_type_id'), table_name='user_notification_preferences')
    op.drop_table('user_notification_preferences')

    op.drop_index(op.f('ix_notification_types_type'), table_name='notification_types')
    op.drop_table('notification_types')
