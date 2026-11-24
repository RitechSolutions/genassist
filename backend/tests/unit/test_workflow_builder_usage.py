"""The Workflow Builder's own spend read: ledger totals per conversation and for the builder agent"""

from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy.dialects import postgresql

import app.db.models  # noqa: F401  (mapper registry)
from app.repositories.llm_usage_read import LlmUsageReadRepository
from app.services.llm_usage_read import LlmUsageReadService


class _Rows:
    def __init__(self, row):
        self._row = row

    def mappings(self):
        return self

    def one(self):
        return self._row


class CapturingDb:
    def __init__(self, row):
        self.statements = []
        self._row = row

    async def execute(self, stmt):
        self.statements.append(stmt)
        return _Rows(self._row)


ROW = {
    "calls": 7, "input_tokens": 1200, "output_tokens": 300, "total_tokens": 1500,
    "cost_usd": Decimal("0.0123"), "unpriced_calls": 1, "test_run_calls": 2, "test_run_cost_usd": Decimal("0.004"),
}


def _sql(stmt):
    return str(stmt.compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}))


@pytest.mark.asyncio
async def test_conversation_totals_filter_on_that_conversation_only():
    db = CapturingDb(ROW)
    conversation_id = uuid4()

    await LlmUsageReadRepository(db).totals(conversation_id=conversation_id)

    sql = _sql(db.statements[0])
    assert f"conversation_id = '{conversation_id}'" in sql and "is_deleted = 0" in sql
    assert "agents" not in sql
    assert "purpose = 'workflow_builder_test'" in sql


@pytest.mark.asyncio
async def test_builder_totals_find_the_agents_by_their_tools_node_not_their_name():
    db = CapturingDb(ROW)

    await LlmUsageReadRepository(db).totals(builder_agents=True)

    sql = _sql(db.statements[0])
    assert "agent_id IN (SELECT agents.id" in sql
    assert "JOIN workflows ON workflows.id = agents.workflow_id" in sql
    assert "jsonb_array_elements(workflows.nodes)" in sql and "'workflowBuilderToolsNode'" in sql
    assert "agents.is_deleted = 0" in sql and "workflows.is_deleted = 0" in sql
    assert "agents.name" not in sql, "a renamed builder must still count"


@pytest.mark.asyncio
async def test_totals_need_a_scope():
    with pytest.raises(ValueError):
        await LlmUsageReadRepository(CapturingDb(ROW)).totals()


class FakeRepo:
    def __init__(self):
        self.calls = []

    async def totals(self, **scope):
        self.calls.append(scope)
        return ROW


@pytest.mark.asyncio
async def test_builder_usage_reports_this_conversation_and_all_time_as_plain_numbers():
    repo = FakeRepo()
    service = LlmUsageReadService(repo, agent_repo=None, workflow_repo=None)
    conversation_id = uuid4()

    usage = await service.builder_usage(conversation_id)

    assert repo.calls == [{"conversation_id": conversation_id}, {"builder_agents": True}]
    assert usage["conversation"] == usage["all_time"] == {
        "calls": 7, "input_tokens": 1200, "output_tokens": 300, "total_tokens": 1500,
        "cost_usd": 0.0123, "unpriced_calls": 1, "test_run_calls": 2, "test_run_cost_usd": 0.004,
    }


@pytest.mark.asyncio
async def test_builder_usage_without_a_conversation_reads_all_time_only():
    repo = FakeRepo()
    usage = await LlmUsageReadService(repo, agent_repo=None, workflow_repo=None).builder_usage(None)

    assert usage["conversation"] is None and repo.calls == [{"builder_agents": True}]
