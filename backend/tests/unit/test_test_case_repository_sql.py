"""Statement shapes the prompt editor's bounded case loading depends on"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from sqlalchemy.dialects import postgresql

from app.db.events.soft_delete import _soft_delete_filter
from app.repositories import test_suite as repositories

SUITE_ID = uuid4()


def _compiled(statement) -> str:
    return str(statement.compile(dialect=postgresql.dialect()))


async def _captured(coro_factory):
    db = AsyncMock()
    db.execute = AsyncMock(return_value=MagicMock())
    repo = repositories.TestCaseRepository(db=db)
    await coro_factory(repo)
    return db.execute.await_args.args[0]


class TestGetCaseIndexForSuite:
    @pytest.mark.asyncio
    async def test_selects_the_index_columns_and_no_jsonb(self):
        statement = await _captured(lambda repo: repo.get_case_index_for_suite(SUITE_ID))

        sql = _compiled(statement)
        assert "test_cases.id" in sql
        assert "test_cases.source_conversation_id" in sql
        assert "test_cases.turn_index" in sql
        for jsonb_column in ("input_data", "expected_output", "tags"):
            assert f"test_cases.{jsonb_column}" not in sql

    @pytest.mark.asyncio
    async def test_orders_by_id_so_the_window_matches_the_full_rows(self):
        statement = await _captured(lambda repo: repo.get_case_index_for_suite(SUITE_ID))

        assert "ORDER BY test_cases.id" in _compiled(statement)

    @pytest.mark.asyncio
    async def test_the_listener_still_hides_soft_deleted_cases(self):
        statement = await _captured(lambda repo: repo.get_case_index_for_suite(SUITE_ID))

        state = SimpleNamespace(is_select=True, execution_options={}, statement=statement)
        _soft_delete_filter(state)
        assert "test_cases.is_deleted =" in _compiled(state.statement)


class TestGetCasesByIds:
    @pytest.mark.asyncio
    async def test_the_suite_predicate_is_conjoined_with_the_id_list(self):
        statement = await _captured(
            lambda repo: repo.get_cases_by_ids(SUITE_ID, [uuid4(), uuid4()])
        )

        where = _compiled(statement).split("WHERE", 1)[1]
        assert "test_cases.suite_id = " in where
        assert "test_cases.id IN " in where
        assert " AND " in where
        assert " OR " not in where

    @pytest.mark.asyncio
    async def test_an_empty_id_list_runs_no_statement(self):
        db = AsyncMock()
        db.execute = AsyncMock(return_value=MagicMock())
        repo = repositories.TestCaseRepository(db=db)

        assert await repo.get_cases_by_ids(SUITE_ID, []) == []
        db.execute.assert_not_awaited()
