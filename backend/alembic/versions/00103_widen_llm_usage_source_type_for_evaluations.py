"""widen llm usage source type for evaluations

Widens the ``source_type`` CHECK on ``llm_usage_events`` and
``llm_usage_capture_runs`` to accept ``evaluation`` beside ``workflow`` and
``llm_analyst``, so evaluation judge calls can be metered in the ledger.

DESTRUCTIVE DOWNGRADE: the narrow constraint cannot coexist with evaluation
rows, so ``downgrade`` hard-deletes every ``source_type = 'evaluation'`` event
and receipt before restoring it. That spend is unrecoverable — judge calls are
logged nowhere else.

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
    for table, name in _CONSTRAINTS:
        op.drop_constraint(name, table, type_="check")
        op.create_check_constraint(name, table, condition)


def upgrade() -> None:
    _swap_source_type_checks(_WIDENED)


def downgrade() -> None:
    for table, _ in _CONSTRAINTS:
        op.execute(sa.text(f"DELETE FROM {table} WHERE source_type = 'evaluation'"))
    _swap_source_type_checks(_ORIGINAL)
