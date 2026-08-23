"""add llm usage cache tokens to non negative check

Extends ck_llm_usage_events_non_negative to also cover the two cache
token columns 00109 added, the same protection every other counter
on this table already has, guarding manual SQL, backfills, and future
writers that application-level clamping does not reach.

Swaps the constraint using low-lock recipe, extended to
resume safely: each step checks pg_constraint first and only runs
what is still outstanding, so a failure partway through can be
retried without manual cleanup.

Downgrade runs before 00109's data guard, so a refusal there can
leave this swap reverted while the revision still reads 00110;
startup verification catches the mismatch, and downgrading to 00109
then upgrading again repairs it.

Revision ID: d6debd295494
Revises: d37941010920
Create Date: 2026-08-23 13:53:56.339795

"""

from typing import List, Optional, Sequence, Tuple, Union

import sqlalchemy as sa

from alembic import op

revision: str = "d6debd295494"
down_revision: Union[str, None] = "d37941010920"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLE = "llm_usage_events"
_CONSTRAINT = "ck_llm_usage_events_non_negative"
_TMP = f"{_CONSTRAINT}__tmp"

_ORIGINAL_CHECK = "input_tokens >= 0 AND output_tokens >= 0 AND total_tokens >= 0 AND call_index >= 0"
_EXTENDED_CHECK = (
    "input_tokens >= 0 AND output_tokens >= 0 AND total_tokens >= 0 AND call_index >= 0"
    " AND cache_read_tokens >= 0 AND cache_creation_tokens >= 0"
)

# Postgres re-renders a CHECK with its own parenthesisation, so the catalog form is not
# the expression above. These are the exact strings pg_get_constraintdef returns.
_ORIGINAL_DEF = (
    "CHECK (((input_tokens >= 0) AND (output_tokens >= 0)"
    " AND (total_tokens >= 0) AND (call_index >= 0)))"
)
_EXTENDED_DEF = (
    "CHECK (((input_tokens >= 0) AND (output_tokens >= 0)"
    " AND (total_tokens >= 0) AND (call_index >= 0)"
    " AND (cache_read_tokens >= 0) AND (cache_creation_tokens >= 0)))"
)

ConstraintState = Optional[Tuple[str, bool]]


def _normalized(definition: str) -> str:
    """Catalog definition with the NOT VALID marker dropped and whitespace collapsed"""
    text = " ".join((definition or "").split())
    marker = " NOT VALID"
    return text[: -len(marker)] if text.endswith(marker) else text


def _observe(bind, name: str) -> ConstraintState:
    row = bind.execute(
        sa.text(
            "SELECT pg_get_constraintdef(oid), convalidated FROM pg_constraint"
            " WHERE conrelid = to_regclass(:table) AND conname = :name AND contype = 'c'"
        ),
        {"table": _TABLE, "name": name},
    ).first()
    return None if row is None else (_normalized(row[0]), bool(row[1]))


def _outstanding_statements(
    final: ConstraintState,
    tmp: ConstraintState,
    current_def: str,
    target_def: str,
    expression: str,
) -> List[str]:
    """The swap statements still to run, given what the catalog already shows"""
    add = f"ALTER TABLE {_TABLE} ADD CONSTRAINT {_TMP} CHECK ({expression}) NOT VALID"
    drop = f"ALTER TABLE {_TABLE} DROP CONSTRAINT {_CONSTRAINT}"
    validate = f"ALTER TABLE {_TABLE} VALIDATE CONSTRAINT {_TMP}"
    rename = f"ALTER TABLE {_TABLE} RENAME CONSTRAINT {_TMP} TO {_CONSTRAINT}"

    if final == (target_def, True) and tmp is None:
        return []
    if final == (current_def, True) and tmp is None:
        return [add, drop, validate, rename]
    if final == (current_def, True) and tmp is not None and tmp[0] == target_def:
        return [drop, *([] if tmp[1] else [validate]), rename]
    if final is None and tmp is not None and tmp[0] == target_def:
        return [*([] if tmp[1] else [validate]), rename]

    raise RuntimeError(
        f"Refusing to swap {_CONSTRAINT} on {_TABLE}: unrecognised constraint state. "
        f"Observed {_CONSTRAINT}={final!r} and {_TMP}={tmp!r}; expected to start from "
        f"{(current_def, True)!r} or to resume a partial swap towards {target_def!r}. "
        "Resolve the constraint by hand before retrying."
    )


def _swap(current_def: str, target_def: str, expression: str) -> None:
    bind = op.get_bind()
    statements = _outstanding_statements(
        _observe(bind, _CONSTRAINT), _observe(bind, _TMP), current_def, target_def, expression
    )
    if not statements:
        return

    with op.get_context().autocommit_block():
        for statement in statements:
            op.execute(statement)


def upgrade() -> None:
    _swap(_ORIGINAL_DEF, _EXTENDED_DEF, _EXTENDED_CHECK)


def downgrade() -> None:
    _swap(_EXTENDED_DEF, _ORIGINAL_DEF, _ORIGINAL_CHECK)
