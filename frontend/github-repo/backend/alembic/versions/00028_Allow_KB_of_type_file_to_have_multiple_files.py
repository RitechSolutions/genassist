"""Allow KB of type file to have multiple files

Revision ID: c999ae176763
Revises: 314b75ba8138
Create Date: 2025-11-25 15:58:29.404711

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'c999ae176763'
down_revision: Union[str, None] = 'd4698bfbfce3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add 'files' column
    op.add_column('knowledge_bases', sa.Column(
        'files', postgresql.JSONB(astext_type=sa.Text()), nullable=True))

    # Migrate existing data from 'file' to 'files' (as array with single string element)
    op.execute("""
        UPDATE knowledge_bases
        SET files = jsonb_build_array(file)
        WHERE file IS NOT NULL
    """)

    # Drop 'file' column
    op.drop_column('knowledge_bases', 'file')


def downgrade() -> None:
    # Add 'file' column
    op.add_column('knowledge_bases', sa.Column(
        'file', sa.String(255), nullable=True))

    # Migrate data back (take first element from files array)
    op.execute("""
        UPDATE knowledge_bases
        SET file = files->>0
        WHERE files IS NOT NULL AND jsonb_array_length(files) > 0
    """)

    # Drop 'files' column
    op.drop_column('knowledge_bases', 'files')
