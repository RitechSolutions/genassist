"""add soft delete column

Revision ID: 83d2486208c0
Revises: 8961aba78fed
Create Date: 2025-05-21 10:41:38.747893

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '83d2486208c0'
down_revision: Union[str, None] = '8961aba78fed'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


TABLES = [
    "agent_knowledge_bases", "agent_tools", "agents", "api_key_roles", "api_keys", "app_settings",
    "audit_log", "conversation_analysis", "conversations", "customers", "data_sources",
    "feature_flags", "job_logs", "jobs", "knowledge_bases", "llm_analyst", "llm_providers",
    "operator_statistics", "operators", "permissions", "recordings", "role_permissions", "roles",
    "tools", "user_roles", "user_types", "users"
]

def upgrade() -> None:
    for table in TABLES:
        op.add_column(table, sa.Column('is_deleted', sa.Integer(), nullable=True))
        op.execute(f"UPDATE {table} SET is_deleted = 0")
        op.alter_column(table, 'is_deleted', nullable=False)

def downgrade() -> None:
    for table in reversed(TABLES):  # Reverse order just in case of FK dependencies
        op.drop_column(table, 'is_deleted')