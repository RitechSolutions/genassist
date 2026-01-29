"""Set default embedding type for existing KBs

This migration sets embedding_type='huggingface' for all existing knowledge bases
that have vector embeddings enabled but no explicit embedding type.

This is needed because the default embedding type is changing from 'huggingface' to 'bedrock'.
By explicitly setting the type for existing KBs, they will continue working as before.

Revision ID: a1b2c3d4e5f6
Revises: f95b2ce2d955
Create Date: 2026-01-29 09:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = 'f95b2ce2d955'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Set embedding_type='huggingface' for all KBs with vector embeddings enabled
    but no explicit embedding_type set.
    """
    op.execute("""
        UPDATE knowledge_bases
        SET rag_config = jsonb_set(
            rag_config,
            '{vector,embedding_type}',
            '"huggingface"'::jsonb,
            true
        )
        WHERE rag_config->'vector'->>'enabled' = 'true'
          AND rag_config->'vector'->>'embedding_type' IS NULL
    """)


def downgrade() -> None:
    """
    Remove the embedding_type field from vector config.
    This reverts to the implicit default behavior.
    """
    op.execute("""
        UPDATE knowledge_bases
        SET rag_config = rag_config #- '{vector,embedding_type}'
        WHERE rag_config->'vector'->>'embedding_type' = 'huggingface'
    """)