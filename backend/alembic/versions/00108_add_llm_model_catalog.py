"""add llm_model_catalog table

Creates ``llm_model_catalog`` — the per-tenant overlay of LLM models that extends
the built-in option lists in ``app/schemas/dynamic_form_schemas/llm_form_schemas.py``.

The table ships **empty on purpose**. The hardcoded schemas remain the source of
truth for every model shipped with the product, and the catalog is appended to
them at request time (see ``LLMProvider.get_configuration_definitions``). An empty
table therefore reproduces the pre-migration behaviour byte for byte, which keeps
this a no-op for tenants that are already live: nothing is copied, nothing drifts,
and shipping a new built-in model still reaches every tenant.

Keyed ``(provider_key, model_key)`` to match ``llm_cost_rates`` so a catalog entry
and its pricing row line up.

Revision ID: c7f1a9d4e620
Revises: b8454171e700
Create Date: 2026-08-20 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "c7f1a9d4e620"
down_revision: Union[str, None] = "b8454171e700"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLE = "llm_model_catalog"
_INDEX = "ix_llm_model_catalog_provider_key"
_UNIQUE_ACTIVE = "uq_llm_model_catalog_provider_model_active"


def upgrade() -> None:
    op.create_table(
        _TABLE,
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("provider_key", sa.String(length=64), nullable=False),
        sa.Column("model_key", sa.String(length=512), nullable=False),
        sa.Column("label", sa.String(length=255), nullable=False),
        sa.Column("is_active", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.Column("created_by", sa.UUID(), nullable=True),
        sa.Column("updated_by", sa.UUID(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=True,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=True,
        ),
        sa.Column("is_deleted", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.PrimaryKeyConstraint("id", name="llm_model_catalog_pk"),
    )
    op.create_index(_INDEX, _TABLE, ["provider_key"], unique=False)
    # Soft-deleted rows must not block re-adding the same model later.
    op.create_index(
        _UNIQUE_ACTIVE,
        _TABLE,
        ["provider_key", "model_key"],
        unique=True,
        postgresql_where=sa.text("is_deleted = 0"),
    )


def downgrade() -> None:
    op.drop_index(_UNIQUE_ACTIVE, table_name=_TABLE)
    op.drop_index(_INDEX, table_name=_TABLE)
    op.drop_table(_TABLE)
