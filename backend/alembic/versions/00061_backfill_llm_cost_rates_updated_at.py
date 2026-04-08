"""backfill llm_cost_rates.updated_at + enforce unique provider/model (active)

Fixes legacy rows that may have NULL updated_at due to a model/schema mismatch.
Also ensures (provider_key, model_key) is unique among non-deleted rows by:
- normalizing keys to lowercase+trim
- soft-deleting duplicates (keeping the most recent row)
- creating a partial unique index for active rows

Revision ID: f1c2d3e4a5b6
Revises: e8f9a0b1c2d3
Create Date: 2026-04-07 12:00:00.000000

"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "f1c2d3e4a5b6"
down_revision: Union[str, None] = "e8f9a0b1c2d3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    conn.execute(
        sa.text(
            """
            UPDATE llm_cost_rates
            SET updated_at = COALESCE(created_at, CURRENT_TIMESTAMP)
            WHERE updated_at IS NULL
            """
        )
    )

    # Normalize keys to match importer behavior (trim + lowercase) to prevent
    # case/whitespace duplicates from surviving.
    conn.execute(
        sa.text(
            """
            UPDATE llm_cost_rates
            SET
              provider_key = LOWER(TRIM(provider_key)),
              model_key = LOWER(TRIM(model_key))
            WHERE
              provider_key IS NOT NULL
              AND model_key IS NOT NULL
            """
        )
    )

    # Soft-delete duplicates (keep the most recent row per provider/model).
    # Uses a window function; marks all but rn=1 as deleted.
    conn.execute(
        sa.text(
            """
            WITH ranked AS (
              SELECT
                id,
                ROW_NUMBER() OVER (
                  PARTITION BY provider_key, model_key
                  ORDER BY COALESCE(updated_at, created_at) DESC, id DESC
                ) AS rn
              FROM llm_cost_rates
              WHERE is_deleted = 0
            )
            UPDATE llm_cost_rates
            SET is_deleted = 1
            WHERE id IN (SELECT id FROM ranked WHERE rn > 1)
            """
        )
    )

    # Enforce uniqueness among active rows only.
    op.create_index(
        "uq_llm_cost_rates_provider_model_active",
        "llm_cost_rates",
        ["provider_key", "model_key"],
        unique=True,
        postgresql_where=sa.text("is_deleted = 0"),
    )


def downgrade() -> None:
    op.drop_index(
        "uq_llm_cost_rates_provider_model_active",
        table_name="llm_cost_rates",
        postgresql_where=sa.text("is_deleted = 0"),
    )

    # Non-destructive: we don't revert timestamps or resurrect duplicates.
    return

