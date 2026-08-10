"""widen llm usage source type for evaluations

Widens the ``source_type`` CHECK on ``llm_usage_events`` and
``llm_usage_capture_runs`` to accept ``evaluation`` beside ``workflow`` and
``llm_analyst``, so evaluation judge calls can be metered in the ledger.

The narrow constraint cannot coexist with evaluation rows, so ``downgrade``
refuses while any event or receipt still carries that source type: judge calls
are logged nowhere else, and deleting them would erase the only record of that
spend. Removing those rows is a deliberate operator decision, taken before the
downgrade rather than silently as part of it.

Swapping a CHECK constraint on a live table normally means DROP + re-CREATE,
which validates the new condition against every existing row while holding an
ACCESS EXCLUSIVE lock for the whole scan — on ``llm_usage_events`` (written on
every LLM call) that blocks all writes for the duration. Instead each table's
swap is: ADD the new constraint NOT VALID (instant, no scan), DROP the old one
(instant), then VALIDATE the new one (scans the table but only needs a SHARE
UPDATE EXCLUSIVE lock, so concurrent reads/writes are unaffected), then rename
it back to the original name. Each of those is issued as its own
autocommitted statement — batching them into one transaction would hold the
DROP's ACCESS EXCLUSIVE lock through the VALIDATE scan and defeat the point.

Revision ID: a5784baf5f4c
Revises: c6974c08b567
Create Date: 2026-07-30 17:08:42.824353

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "a5784baf5f4c"
down_revision: Union[str, None] = "c6974c08b567"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_CONSTRAINTS = (
    ("llm_usage_events", "ck_llm_usage_events_source_type"),
    ("llm_usage_capture_runs", "ck_llm_usage_capture_runs_source_type"),
)

_WIDENED = "source_type IN ('workflow', 'llm_analyst', 'evaluation')"
_ORIGINAL = "source_type IN ('workflow', 'llm_analyst')"


def _swap_source_type_checks(condition: str) -> None:
    # Each statement autocommits on its own — see the module docstring for why
    # batching these into one transaction would reintroduce the write lock.
    with op.get_context().autocommit_block():
        for table, name in _CONSTRAINTS:
            tmp_name = f"{name}__tmp"
            op.execute(f"ALTER TABLE {table} ADD CONSTRAINT {tmp_name} CHECK ({condition}) NOT VALID")
            op.execute(f"ALTER TABLE {table} DROP CONSTRAINT {name}")
            op.execute(f"ALTER TABLE {table} VALIDATE CONSTRAINT {tmp_name}")
            op.execute(f"ALTER TABLE {table} RENAME CONSTRAINT {tmp_name} TO {name}")


def upgrade() -> None:
    _swap_source_type_checks(_WIDENED)


def downgrade() -> None:
    bind = op.get_bind()
    for table, _ in _CONSTRAINTS:
        count = bind.execute(sa.text(f"SELECT COUNT(*) FROM {table} WHERE source_type = 'evaluation'")).scalar_one()
        if count:
            raise RuntimeError(
                f"Refusing downgrade: {count} evaluation row(s) in {table} would become invalid. "
                "Delete them explicitly first, judge spend is logged nowhere else."
            )
    _swap_source_type_checks(_ORIGINAL)
