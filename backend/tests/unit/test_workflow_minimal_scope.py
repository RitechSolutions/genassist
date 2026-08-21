"""The minimal workflow list must not leak group-scoped agent names."""

from unittest.mock import patch

from sqlalchemy.dialects import postgresql

import app.db.events.group_scope as group_scope
import app.db.models.test_suite  # noqa: F401 - registers the ORM mappers
from app.repositories.workflow import WorkflowRepository


def _compiled(scoped_list: bool = False, **context) -> str:
    with patch.object(group_scope, "context", context), patch.object(
        group_scope, "current_user_is_admin", lambda: False
    ):
        statement = WorkflowRepository._minimal_select(WorkflowRepository)
        if scoped_list:
            statement = statement.where(WorkflowRepository._visible_agent())
    return str(statement.compile(dialect=postgresql.dialect()))


def test_agent_name_is_group_scoped_for_a_regular_user():
    sql = _compiled(group_id="g-1", user_id="u-1", supervised_group_ids=[])

    # The name is only read for agents the caller's group owns.
    assert "agents.created_by IN" in sql
    assert "THEN agents.name END AS agent_name" in sql


def test_agent_name_is_unscoped_without_an_auth_context():
    """Background jobs have no context; scoping is skipped, as everywhere else."""
    sql = _compiled()

    assert "agents.created_by IN" not in sql
    assert "agent_name" in sql


def _row_filter(sql: str) -> str:
    """The statement's own WHERE — not the CASE, and not the scope subquery's."""
    from_clause = sql[sql.index("FROM workflows"):]
    return from_clause[from_clause.index("WHERE"):]


def test_the_visible_list_only_returns_agents_the_caller_can_see():
    """get_visible_minimal filters rows, so the picker matches Agent Studio."""
    sql = _compiled(scoped_list=True, group_id="g-1", user_id="u-1", supervised_group_ids=[])

    where = _row_filter(sql)
    assert "agents.is_deleted" in where
    assert "agents.created_by IN" in where


def test_the_internal_list_and_lookups_stay_unscoped():
    """Internal callers need every row — a bundle import resolves a workflow's
    sibling versions this way — and a stored reference must still resolve."""
    where = _row_filter(_compiled(group_id="g-1", user_id="u-1", supervised_group_ids=[]))

    assert "agents.created_by IN" not in where
    assert "agents.is_deleted" not in where


def test_active_version_pointer_is_never_scoped():
    """The pointer must read the same for every caller, or a version would look
    active to some and not to others."""
    scoped = _compiled(group_id="g-1", user_id="u-1", supervised_group_ids=[])

    assert "CASE WHEN (agents.workflow_id = workflows.id)" in scoped
