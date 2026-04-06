"""mcp_servers: add auth_type and auth_values (OAuth2 / JSONB); keep 00030 columns

Revision ID: a1b2c3d4e5f7
Revises: e8f9a0b1c2d3
Create Date: 2026-04-03 12:00:00.000000

Legacy columns come only from 00030_add_mcp_servers_tables (e.g. api_key_encrypted,
api_key_hash). This revision does not drop or alter those columns. New behavior is
carried by auth_type and auth_values; existing API key material remains in the
original columns.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "a1b2c3d4e5f7"
down_revision: Union[str, None] = "e8f9a0b1c2d3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _mcp_server_column_names(bind) -> set[str]:
    insp = inspect(bind)
    if not insp.has_table("mcp_servers"):
        return set()
    return {c["name"] for c in insp.get_columns("mcp_servers")}


def _ensure_oauth_unique_index() -> None:
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_mcp_oauth_issuer_client
        ON mcp_servers (
            (auth_values->>'oauth2_issuer_url'),
            (auth_values->>'oauth2_client_id_hash')
        )
        WHERE auth_type = 'oauth2' AND is_deleted = 0
          AND auth_values->>'oauth2_client_id_hash' IS NOT NULL;
        """
    )


def upgrade() -> None:
    bind = op.get_bind()
    cols = _mcp_server_column_names(bind)

    if "auth_type" in cols and "auth_values" in cols:
        _ensure_oauth_unique_index()
        return

    if "auth_type" not in cols:
        op.add_column(
            "mcp_servers",
            sa.Column("auth_type", sa.String(length=32), server_default="api_key", nullable=False),
        )
    if "auth_values" not in cols:
        op.add_column(
            "mcp_servers",
            sa.Column(
                "auth_values",
                JSONB(astext_type=sa.Text()),
                nullable=False,
                server_default=sa.text("'{}'::jsonb"),
            ),
        )

    _ensure_oauth_unique_index()


def downgrade() -> None:
    bind = op.get_bind()
    cols = _mcp_server_column_names(bind)

    if "auth_type" not in cols and "auth_values" not in cols:
        return

    op.execute("DROP INDEX IF EXISTS uq_mcp_oauth_issuer_client;")

    if "auth_values" in cols:
        op.drop_column("mcp_servers", "auth_values")
    if "auth_type" in cols:
        op.drop_column("mcp_servers", "auth_type")
