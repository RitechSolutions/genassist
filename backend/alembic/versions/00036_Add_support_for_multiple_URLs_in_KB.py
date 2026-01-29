"""Add support for multiple URLs in KB

Revision ID: f95b2ce2d955
Revises: c7f8d9e0f123
Create Date: 2026-01-26 16:17:29.470914

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'f95b2ce2d955'
down_revision: Union[str, None] = 'c7f8d9e0f123'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('knowledge_bases', sa.Column(
        'urls', postgresql.JSONB(astext_type=sa.Text()), nullable=True))

    # Migrate existing data from 'url' to 'urls' (as array with single string element)
    op.execute("""
        UPDATE knowledge_bases
        SET urls = jsonb_build_array(url)
        WHERE url IS NOT NULL
    """)

    op.drop_column('knowledge_bases', 'url')


def downgrade() -> None:
    op.add_column('knowledge_bases', sa.Column(
        'url', sa.VARCHAR(length=255), autoincrement=False, nullable=True))

    # Migrate data back (take first element from urls array)
    op.execute("""
        UPDATE knowledge_bases
        SET url = urls->>0
        WHERE urls IS NOT NULL AND jsonb_array_length(urls) > 0
    """)

    op.drop_column('knowledge_bases', 'urls')
