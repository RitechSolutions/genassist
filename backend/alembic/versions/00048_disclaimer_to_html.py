"""convert disclaimer fields to single html column

Revision ID: e3f4a5b6c7d8
Revises: d2e3f4a5b6c7
Create Date: 2026-03-09

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "e3f4a5b6c7d8"
down_revision: Union[str, None] = "d2e3f4a5b6c7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Add new HTML column
    op.add_column("agents", sa.Column("input_disclaimer_html", sa.Text(), nullable=True))

    # 2. Migrate existing data: combine text + link into HTML
    op.execute("""
        UPDATE agents
        SET input_disclaimer_html = CASE
            WHEN input_disclaimer IS NOT NULL AND input_disclaimer != ''
                 AND input_disclaimer_link_url IS NOT NULL AND input_disclaimer_link_url != ''
            THEN input_disclaimer || ' <a href="' || input_disclaimer_link_url
                 || '" target="_blank" rel="noopener noreferrer">'
                 || COALESCE(NULLIF(input_disclaimer_link_label, ''), input_disclaimer_link_url)
                 || '</a>'
            WHEN input_disclaimer IS NOT NULL AND input_disclaimer != ''
            THEN input_disclaimer
            WHEN input_disclaimer_link_url IS NOT NULL AND input_disclaimer_link_url != ''
            THEN '<a href="' || input_disclaimer_link_url
                 || '" target="_blank" rel="noopener noreferrer">'
                 || COALESCE(NULLIF(input_disclaimer_link_label, ''), input_disclaimer_link_url)
                 || '</a>'
            ELSE NULL
        END
        WHERE input_disclaimer IS NOT NULL OR input_disclaimer_link_url IS NOT NULL
    """)

    # 3. Drop old columns
    op.drop_column("agents", "input_disclaimer")
    op.drop_column("agents", "input_disclaimer_link_url")
    op.drop_column("agents", "input_disclaimer_link_label")


def downgrade() -> None:
    # Re-add old columns
    op.add_column("agents", sa.Column("input_disclaimer", sa.String(length=500), nullable=True))
    op.add_column("agents", sa.Column("input_disclaimer_link_url", sa.String(length=500), nullable=True))
    op.add_column("agents", sa.Column("input_disclaimer_link_label", sa.String(length=200), nullable=True))

    # Best-effort: put HTML content into input_disclaimer (lossy)
    op.execute("""
        UPDATE agents
        SET input_disclaimer = input_disclaimer_html
        WHERE input_disclaimer_html IS NOT NULL
    """)

    op.drop_column("agents", "input_disclaimer_html")
