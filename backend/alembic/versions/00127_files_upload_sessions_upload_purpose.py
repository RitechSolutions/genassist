"""files_upload_sessions_upload_purpose

Adds an additive ``upload_purpose`` column to ``files_upload_sessions`` so a
chunked or direct-S3 upload started for Train Data Source
(``"training_data"``) is checked against the training upload limit on every
chunk, on complete and on finalize. NULL keeps the regular File Manager limit,
so in-flight rows behave as before.

Revision ID: c3a9d27e5b41
Revises: a601f9fbdddb
Create Date: 2026-10-23 15:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c3a9d27e5b41"
down_revision: Union[str, None] = "a601f9fbdddb"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "files_upload_sessions",
        sa.Column("upload_purpose", sa.String(length=32), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("files_upload_sessions", "upload_purpose")
