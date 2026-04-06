"""mcp_servers: auth_type, oauth2 support, auth_values JSONB (merged 00061+00062)

Revision ID: a1b2c3d4e5f7
Revises: e8f9a0b1c2d3
Create Date: 2026-04-03 12:00:00.000000

If you previously applied only revision f1a2b3c4d5e6 (old split migration),
downgrade to e8f9a0b1c2d3 or stamp before upgrading with this file.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "a1b2c3d4e5f7"
down_revision: Union[str, None] = "e8f9a0b1c2d3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "mcp_servers",
        sa.Column("auth_type", sa.String(length=32), server_default="api_key", nullable=False),
    )
    op.add_column(
        "mcp_servers",
        sa.Column("auth_values", JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.execute(
        """
        UPDATE mcp_servers SET auth_values = jsonb_build_object(
            'api_key_encrypted', api_key_encrypted,
            'api_key_hash', api_key_hash
        );
        """
    )
    op.alter_column("mcp_servers", "auth_values", nullable=False)

    op.execute("DROP INDEX IF EXISTS idx_api_key_hash;")
    op.execute("DROP INDEX IF EXISTS ix_mcp_servers_api_key_hash;")

    op.drop_column("mcp_servers", "api_key_hash")
    op.drop_column("mcp_servers", "api_key_encrypted")

    op.execute(
        """
        CREATE UNIQUE INDEX uq_mcp_oauth_issuer_client
        ON mcp_servers (
            (auth_values->>'oauth2_issuer_url'),
            (auth_values->>'oauth2_client_id_hash')
        )
        WHERE auth_type = 'oauth2' AND is_deleted = 0
          AND auth_values->>'oauth2_client_id_hash' IS NOT NULL;
        """
    )
    op.execute(
        """
        CREATE INDEX idx_mcp_auth_api_key_hash
        ON mcp_servers ((auth_values->>'api_key_hash'))
        WHERE auth_type = 'api_key' AND is_deleted = 0;
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_mcp_auth_api_key_hash;")
    op.execute("DROP INDEX IF EXISTS uq_mcp_oauth_issuer_client;")

    op.add_column("mcp_servers", sa.Column("api_key_encrypted", sa.String(), nullable=True))
    op.add_column("mcp_servers", sa.Column("api_key_hash", sa.String(length=255), nullable=True))
    op.add_column("mcp_servers", sa.Column("oauth2_client_id_encrypted", sa.Text(), nullable=True))
    op.add_column("mcp_servers", sa.Column("oauth2_client_secret_encrypted", sa.Text(), nullable=True))
    op.add_column("mcp_servers", sa.Column("oauth2_issuer_url", sa.String(length=512), nullable=True))
    op.add_column("mcp_servers", sa.Column("oauth2_audience", sa.String(length=512), nullable=True))
    op.add_column("mcp_servers", sa.Column("oauth2_client_id_hash", sa.String(length=255), nullable=True))

    op.execute(
        """
        UPDATE mcp_servers SET
            api_key_encrypted = auth_values->>'api_key_encrypted',
            api_key_hash = auth_values->>'api_key_hash',
            oauth2_client_id_encrypted = auth_values->>'oauth2_client_id_encrypted',
            oauth2_client_secret_encrypted = auth_values->>'oauth2_client_secret_encrypted',
            oauth2_issuer_url = auth_values->>'oauth2_issuer_url',
            oauth2_audience = NULLIF(auth_values->>'oauth2_audience', ''),
            oauth2_client_id_hash = auth_values->>'oauth2_client_id_hash'
        WHERE auth_values IS NOT NULL;
        """
    )

    op.drop_column("mcp_servers", "auth_values")

    op.drop_column("mcp_servers", "oauth2_client_id_hash")
    op.drop_column("mcp_servers", "oauth2_audience")
    op.drop_column("mcp_servers", "oauth2_issuer_url")
    op.drop_column("mcp_servers", "oauth2_client_secret_encrypted")
    op.drop_column("mcp_servers", "oauth2_client_id_encrypted")
    op.alter_column("mcp_servers", "api_key_hash", existing_type=sa.String(length=255), nullable=False)
    op.alter_column("mcp_servers", "api_key_encrypted", existing_type=sa.String(), nullable=False)
    op.drop_column("mcp_servers", "auth_type")

    op.create_index("idx_api_key_hash", "mcp_servers", ["api_key_hash"], unique=False)
    op.create_index(op.f("ix_mcp_servers_api_key_hash"), "mcp_servers", ["api_key_hash"], unique=False)
