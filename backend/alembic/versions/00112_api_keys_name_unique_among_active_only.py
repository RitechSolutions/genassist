"""api_keys: name unique among active (non soft-deleted) rows only

API keys are soft-deleted (is_deleted = 1), but the original ``api_keys_unique``
constraint covered every row. A deleted key therefore kept its name reserved
forever and re-creating a key with that name failed with a duplicate-key error.

Replace the full constraint with a partial unique index scoped to active rows,
so soft-deleted keys release their name while active keys stay unique.

Revision ID: 8f3c2a91b7d4
Revises: 454448e85877
Create Date: 2026-09-22 10:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "8f3c2a91b7d4"
down_revision: Union[str, None] = "454448e85877"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLE = "api_keys"
_OLD_CONSTRAINT = "api_keys_unique"
_NEW_INDEX = "api_keys_name_active_unique"


def upgrade() -> None:
    op.drop_constraint(_OLD_CONSTRAINT, _TABLE, type_="unique")
    op.create_index(
        _NEW_INDEX,
        _TABLE,
        ["name"],
        unique=True,
        postgresql_where=sa.text("is_deleted = 0"),
    )


def downgrade() -> None:
    op.drop_index(_NEW_INDEX, table_name=_TABLE)
    # Soft-deleted rows may now share a name with an active one (or with each
    # other). Free those names first so the full constraint can be restored.
    op.execute(
        f"""
        UPDATE {_TABLE} d
        SET name = d.name || ' (deleted ' || d.id::text || ')'
        WHERE d.is_deleted = 1
          AND EXISTS (
              SELECT 1 FROM {_TABLE} o
              WHERE o.name = d.name AND o.id <> d.id
          )
        """
    )
    op.create_unique_constraint(_OLD_CONSTRAINT, _TABLE, ["name"])
