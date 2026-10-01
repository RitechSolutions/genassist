"""remove OTHER from model_type_enum

Finishes the "Other" (bring-your-own pretrained model) removal started in the
API schema (Pydantic ModelType no longer has OTHER). This migration shrinks
the Postgres enum to match by recreating it without OTHER - Postgres has no
``ALTER TYPE ... DROP VALUE``, so the standard workaround is rename the old
type, create a new one without the dropped value, repoint the column at it
via a text cast, then drop the old type.

Refuses to run if any ml_models row still has model_type = 'OTHER': there is
no correct automatic remapping to one of the 15 remaining specific algorithm
types (that would silently misrepresent what the model actually is), so an
operator has to resolve those rows by hand first - delete them, or reassign
each to whichever algorithm it actually was trained with.

Revision ID: e1a2b3c4d5f6
Revises: 3c9d1e7a5b2f
Create Date: 2026-09-30 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "e1a2b3c4d5f6"
down_revision: Union[str, None] = "3c9d1e7a5b2f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_REMAINING_VALUES = [
    "XGBOOST",
    "LIGHTGBM",
    "CATBOOST",
    "RANDOM_FOREST",
    "EXTRA_TREES",
    "GRADIENT_BOOSTING",
    "DECISION_TREE",
    "LINEAR_REGRESSION",
    "RIDGE_REGRESSION",
    "LASSO_REGRESSION",
    "ELASTIC_NET",
    "LOGISTIC_REGRESSION",
    "SVM",
    "KNN",
    "NEURAL_NETWORK",
]


def _recreate_enum(values: list[str]) -> None:
    values_sql = ", ".join(f"'{v}'" for v in values)
    op.execute("ALTER TYPE model_type_enum RENAME TO model_type_enum_old")
    op.execute(f"CREATE TYPE model_type_enum AS ENUM ({values_sql})")
    op.execute(
        "ALTER TABLE ml_models "
        "ALTER COLUMN model_type TYPE model_type_enum "
        "USING model_type::text::model_type_enum"
    )
    op.execute("DROP TYPE model_type_enum_old")


def upgrade() -> None:
    conn = op.get_bind()
    count = conn.execute(
        sa.text("SELECT COUNT(*) FROM ml_models WHERE model_type = 'OTHER'")
    ).scalar_one()
    if count:
        raise RuntimeError(
            f"Cannot drop 'OTHER' from model_type_enum: {count} ml_models row(s) "
            "still have model_type = 'OTHER'. Reassign or delete them first - "
            "there is no safe automatic mapping to one of the specific "
            "algorithm types."
        )

    _recreate_enum(_REMAINING_VALUES)


def downgrade() -> None:
    _recreate_enum(_REMAINING_VALUES + ["OTHER"])
