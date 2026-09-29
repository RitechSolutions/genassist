"""Unit tests for group-scoped row filtering, asserting the SQL it emits"""

from contextlib import contextmanager
from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.dialects import postgresql
from starlette_context import context, request_cycle_context

import app.db.models  # noqa: F401 — registers mappers for ORM compilation
import app.db.models.test_suite  # noqa: F401
from app.db.events.group_scope import _group_scope_filter, get_group_scope_clause
from app.db.models.agent import AgentModel
from app.db.models.conversation import ConversationModel


def _sql(stmt) -> str:
    return str(stmt.compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}))


@contextmanager
def caller(*, user_id=None, group_id=None, supervised=()):
    with request_cycle_context():
        context["user_id"] = user_id
        context["group_id"] = group_id
        context["supervised_group_ids"] = list(supervised)
        context["user_roles"] = [SimpleNamespace(name="operator")]
        yield


def _listener_sql(model_cls):
    """Run the do_orm_execute listener over a bare ORM select and compile the result."""
    state = SimpleNamespace(is_select=True, execution_options={}, statement=select(model_cls))
    _group_scope_filter(state)
    return _sql(state.statement)


def test_supervisor_criteria_union_own_group_with_supervised_groups():
    own_group = uuid4()
    supervised = [uuid4(), uuid4()]
    with caller(user_id=uuid4(), group_id=own_group, supervised=supervised):
        sql = _sql(select(AgentModel.id).where(get_group_scope_clause(AgentModel)))

    for group_id in [own_group, *supervised]:
        assert f"'{group_id}'" in sql


def test_supervisor_conversation_criteria_union_own_group_with_supervised_groups():
    own_group = uuid4()
    supervised = [uuid4()]
    with caller(user_id=uuid4(), group_id=own_group, supervised=supervised):
        sql = _sql(select(ConversationModel.id).where(get_group_scope_clause(ConversationModel)))

    assert "conversations.group_id IN" in sql
    for group_id in [own_group, *supervised]:
        assert f"'{group_id}'" in sql


def test_listener_criteria_carry_no_groups_from_the_previous_caller():
    """The lambda is compiled once per class — its group ids must stay per-request."""
    first_group, first_supervised = uuid4(), uuid4()
    with caller(user_id=uuid4(), group_id=first_group, supervised=[first_supervised]):
        first = _listener_sql(AgentModel)

    second_group, second_supervised = uuid4(), uuid4()
    with caller(user_id=uuid4(), group_id=second_group, supervised=[second_supervised, uuid4()]):
        second = _listener_sql(AgentModel)

    assert f"'{first_group}'" in first and f"'{first_supervised}'" in first
    assert f"'{second_group}'" in second and f"'{second_supervised}'" in second
    assert str(first_group) not in second
    assert str(first_supervised) not in second


@pytest.mark.parametrize("model_cls", [AgentModel, ConversationModel])
def test_non_supervisors_keep_the_group_equality_form(model_cls):
    group_id = uuid4()
    with caller(user_id=uuid4(), group_id=group_id):
        assert f"users.group_id = '{group_id}'" in _listener_sql(model_cls)
