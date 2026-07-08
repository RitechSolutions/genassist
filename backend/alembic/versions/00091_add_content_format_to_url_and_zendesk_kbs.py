"""add content_format to url and zendesk kbs

Revision ID: c09bc3d15d9b
Revises: 66c71887a6da
Create Date: 2026-07-08 15:38:56.959558

"""
from typing import Sequence, Union

from alembic import op

revision: str = 'c09bc3d15d9b'
down_revision: Union[str, None] = '66c71887a6da'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE knowledge_bases
        SET extra_metadata = jsonb_set(
            coalesce(extra_metadata, '{}'::jsonb),
            '{content_format}',
            to_jsonb(
                CASE
                    WHEN coalesce((extra_metadata->>'allow_html_content')::boolean, false)
                    THEN 'html'
                    ELSE 'text'
                END
            )
        ) - 'allow_html_content'
        WHERE type IN ('url', 'zendesk')
        """
    )


def downgrade() -> None:
    op.execute(
        """
        UPDATE knowledge_bases
        SET extra_metadata = jsonb_set(
            coalesce(extra_metadata, '{}'::jsonb),
            '{allow_html_content}',
            to_jsonb(coalesce(extra_metadata->>'content_format', '') = 'html')
        ) - 'content_format'
        WHERE type = 'zendesk'
        """
    )
    op.execute(
        """
        UPDATE knowledge_bases
        SET extra_metadata = extra_metadata - 'content_format'
        WHERE type = 'url'
        """
    )