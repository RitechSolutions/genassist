"""files_upload_sessions_upload_mode

Adds an additive ``upload_mode`` column to ``files_upload_sessions`` so the
service layer can disambiguate the legacy server-staged chunked flow
("server_chunked") from the new direct browser -> S3 presigned PUT flow
("direct_s3"). The column is nullable for full backward compatibility with
in-flight rows; new code should always set it explicitly.

Revision ID: b85c0d9e7f12
Revises: f1a2b3c4d5e6
Create Date: 2026-04-29 12:35:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b85c0d9e7f12"
down_revision: Union[str, None] = "f1a2b3c4d5e6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "files_upload_sessions",
        sa.Column("upload_mode", sa.String(length=32), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("files_upload_sessions", "upload_mode")
