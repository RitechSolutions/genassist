"""Statement shapes the prompt-editor repositories depend on"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from sqlalchemy.dialects import postgresql

import app.db.events.group_scope as group_scope
import app.db.models.test_suite  # noqa: F401 - registers TestSuiteModel for PromptConfigModel.gold_suite
from app.db.events.soft_delete import SOFT_DELETE_FLAG, _soft_delete_filter
from app.repositories.prompt_editor import PromptVersionRepository
from app.repositories.workflow import WorkflowRepository

CONTEXT = (uuid4(), "n1", "systemPrompt")


def _compiled(statement) -> str:
    return str(statement.compile(dialect=postgresql.dialect()))


async def _captured(coro_factory):
    db = AsyncMock()
    db.execute = AsyncMock(return_value=MagicMock())
    repo = PromptVersionRepository(db=db)
    await coro_factory(repo)
    return db.execute.await_args.args[0]


def _access_select_sql(**context) -> str:
    with patch.object(group_scope, "context", context), patch.object(
        group_scope, "current_user_is_admin", lambda: False
    ):
        return _compiled(WorkflowRepository._access_select(WorkflowRepository))


class TestAccessSelect:
    def test_a_live_workflow_is_found_for_every_caller(self):
        sql = _access_select_sql(group_id="g-1", user_id="u-1", supervised_group_ids=[])

        assert "workflows.nodes" in sql
        assert "workflows.is_deleted" in sql
        assert "JOIN agents" not in sql
        assert "agents.created_by IN" not in sql


class TestNextVersionNumber:
    @pytest.mark.asyncio
    async def test_counts_soft_deleted_rows(self):
        statement = await _captured(lambda repo: repo.next_version_number(*CONTEXT))

        assert statement.get_execution_options().get(SOFT_DELETE_FLAG) is True

        state = SimpleNamespace(
            is_select=True,
            execution_options=dict(statement.get_execution_options()),
            statement=statement,
        )
        _soft_delete_filter(state)
        assert "is_deleted" not in _compiled(state.statement)

    @pytest.mark.asyncio
    async def test_without_the_flag_the_listener_would_hide_them(self):
        statement = await _captured(lambda repo: repo.next_version_number(*CONTEXT))

        state = SimpleNamespace(is_select=True, execution_options={}, statement=statement)
        _soft_delete_filter(state)
        assert "prompt_versions.is_deleted =" in _compiled(state.statement)


class TestDeactivateAllForContext:
    @pytest.mark.asyncio
    async def test_updates_only_the_live_active_rows_of_the_context(self):
        statement = await _captured(lambda repo: repo.deactivate_all_for_context(*CONTEXT))

        sql = _compiled(statement)
        assert sql.startswith("UPDATE prompt_versions SET")
        assert "is_active=" in sql
        assert "prompt_versions.is_active IS true" in sql
        assert "prompt_versions.is_deleted =" in sql
