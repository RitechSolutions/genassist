"""add_dashboard_analytics_indexes

Adds indexes supporting the dashboard analytics endpoints
(/dashboard/summary, /dashboard/agents):

- transcript_messages (conversation_id, sequence_number): supports the
  m1->m2 self-join used to compute average response time.
- conversations (conversation_date): supports the date-range filters in
  get_avg_response_time / get_workflow_runs_count and the now date-bounded
  per-operator response-time query.
- conversations (operator_id): supports the per-operator filters/group-bys
  in get_agents_with_stats.

Indexes are created CONCURRENTLY to avoid taking a blocking lock on these
large tables in production.

Revision ID: 753019ca4eb2
Revises: 5d4d7a65f44b
Create Date: 2026-06-16 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '753019ca4eb2'
down_revision: Union[str, None] = '5d4d7a65f44b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.get_context().autocommit_block():
        op.create_index(
            "ix_transcript_messages_conv_seq",
            "transcript_messages",
            ["conversation_id", "sequence_number"],
            unique=False,
            postgresql_concurrently=True,
            if_not_exists=True,
        )
        op.create_index(
            "ix_conversations_conversation_date",
            "conversations",
            ["conversation_date"],
            unique=False,
            postgresql_concurrently=True,
            if_not_exists=True,
        )
        op.create_index(
            "ix_conversations_operator_id",
            "conversations",
            ["operator_id"],
            unique=False,
            postgresql_concurrently=True,
            if_not_exists=True,
        )


def downgrade() -> None:
    with op.get_context().autocommit_block():
        op.drop_index(
            "ix_conversations_operator_id",
            table_name="conversations",
            postgresql_concurrently=True,
            if_exists=True,
        )
        op.drop_index(
            "ix_conversations_conversation_date",
            table_name="conversations",
            postgresql_concurrently=True,
            if_exists=True,
        )
        op.drop_index(
            "ix_transcript_messages_conv_seq",
            table_name="transcript_messages",
            postgresql_concurrently=True,
            if_exists=True,
        )