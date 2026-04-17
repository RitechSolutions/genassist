"""add indexes to evaluation-related tables

Adds missing indexes on foreign key columns used in common queries:
- test_cases.suite_id
- test_runs.suite_id
- test_results.run_id
- test_results.case_id
- test_evaluations.suite_id

Revision ID: b1a3ac1f5fe2
Revises: b3c4d5e6f7a8
Create Date: 2026-04-09 12:00:00.000000

"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "b1a3ac1f5fe2"
down_revision: Union[str, None] = "b3c4d5e6f7a8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index("ix_test_cases_suite_id", "test_cases", ["suite_id"])
    op.create_index("ix_test_runs_suite_id", "test_runs", ["suite_id"])
    op.create_index("ix_test_results_run_id", "test_results", ["run_id"])
    op.create_index("ix_test_results_case_id", "test_results", ["case_id"])
    op.create_index("ix_test_evaluations_suite_id", "test_evaluations", ["suite_id"])


def downgrade() -> None:
    op.drop_index("ix_test_evaluations_suite_id", table_name="test_evaluations")
    op.drop_index("ix_test_results_case_id", table_name="test_results")
    op.drop_index("ix_test_results_run_id", table_name="test_results")
    op.drop_index("ix_test_runs_suite_id", table_name="test_runs")
    op.drop_index("ix_test_cases_suite_id", table_name="test_cases")
