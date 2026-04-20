"""mcp oauth2: auth_values JSONB + issuer URL index

Revision ID: a9d1c4e2b7f0
Revises: 6ef6b6d3a473
Create Date: 2026-04-08 12:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "a9d1c4e2b7f0"
down_revision: Union[str, None] = "6ef6b6d3a473"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _mcp_server_column_names(bind) -> set[str]:
    insp = inspect(bind)
    if not insp.has_table("mcp_servers"):
        return set()
    return {c["name"] for c in insp.get_columns("mcp_servers")}


def _ensure_oauth_issuer_url_unique_index() -> None:
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_mcp_oauth_issuer_client
        ON mcp_servers (
            (auth_values->>'oauth2_issuer_url'),
            (auth_values->>'oauth2_client_id_hash')
        )
        WHERE auth_type = 'oauth2' AND is_deleted = 0
          AND auth_values->>'oauth2_client_id_hash' IS NOT NULL
          AND coalesce(btrim(auth_values->>'oauth2_issuer_url'), '') <> '';
        """
    )


def upgrade() -> None:
    bind = op.get_bind()
    cols = _mcp_server_column_names(bind)

    # Ensure columns exist (squashed from the prior revision).
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

    # Legacy columns from 00030: now that auth material lives in auth_values (and oauth2 rows are valid),
    # these must be nullable or inserts/updates can fail on NOT NULL constraints.
    if "api_key_encrypted" in cols:
        op.alter_column("mcp_servers", "api_key_encrypted", nullable=True)
    if "api_key_hash" in cols:
        op.alter_column("mcp_servers", "api_key_hash", nullable=True)

    # Backfill auth_values from legacy api_key columns (00030) when present.
    #
    # Older deployments stored api_key material directly on mcp_servers as:
    # - api_key_encrypted (string)
    # - api_key_hash      (string)
    #
    # This migration squashes prior revisions, so we defensively migrate those
    # columns into auth_values if they still exist. This is safe to run multiple
    # times and won't overwrite oauth2 entries.
    if "api_key_encrypted" in cols and "api_key_hash" in cols:
        op.execute(
            """
            UPDATE mcp_servers
            SET
              auth_type = COALESCE(NULLIF(auth_type, ''), 'api_key'),
              auth_values = auth_values
                || jsonb_build_object(
                  'api_key_encrypted', api_key_encrypted,
                  'api_key_hash', api_key_hash
                )
            WHERE
              COALESCE(NULLIF(auth_type, ''), 'api_key') = 'api_key'
              AND api_key_hash IS NOT NULL
              AND (
                auth_values IS NULL
                OR auth_values = '{}'::jsonb
                OR auth_values->>'api_key_hash' IS NULL
              );
            """
        )

    # Ensure we don't keep both index flavors around.
    op.execute("DROP INDEX IF EXISTS uq_mcp_oauth_issuer_client;")

    _ensure_oauth_issuer_url_unique_index()


def downgrade() -> None:
    bind = op.get_bind()
    cols = _mcp_server_column_names(bind)

    op.execute("DROP INDEX IF EXISTS uq_mcp_oauth_issuer_client;")

    # Squashed downgrade: remove the new auth columns too.
    if "auth_values" in cols:
        op.drop_column("mcp_servers", "auth_values")
    if "auth_type" in cols:
        op.drop_column("mcp_servers", "auth_type")

