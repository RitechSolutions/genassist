"""expand model_type_enum with additional model types

Adds the model types now supported by the train model workflow node and
ML model registry: lightgbm, catboost, extra_trees, gradient_boosting,
decision_tree, ridge_regression, lasso_regression, elastic_net, svm, knn,
neural_network. (catboost was already used by the Pydantic schema but was
never added to the Postgres enum, so creating an ML model with that type
would previously fail at the DB layer.)

Revision ID: 0af5effac072
Revises: c41d7ab35f92
Create Date: 2026-08-27 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op

revision: str = "0af5effac072"
down_revision: Union[str, None] = "c41d7ab35f92"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_NEW_VALUES = [
    "LIGHTGBM",
    "CATBOOST",
    "EXTRA_TREES",
    "GRADIENT_BOOSTING",
    "DECISION_TREE",
    "RIDGE_REGRESSION",
    "LASSO_REGRESSION",
    "ELASTIC_NET",
    "SVM",
    "KNN",
    "NEURAL_NETWORK",
]


def upgrade() -> None:
    # ALTER TYPE ... ADD VALUE cannot run inside a regular transaction block;
    # autocommit_block() runs each statement outside of Alembic's wrapping transaction.
    with op.get_context().autocommit_block():
        for value in _NEW_VALUES:
            op.execute(f"ALTER TYPE model_type_enum ADD VALUE IF NOT EXISTS '{value}'")


def downgrade() -> None:
    # Postgres does not support removing values from an enum type. Values added
    # above are left in place; the application layer stops emitting them.
    pass