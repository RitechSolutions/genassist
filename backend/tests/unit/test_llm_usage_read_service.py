"""Unit tests for LlmUsageReadService canonical cost/coverage math"""

from decimal import Decimal

import pytest

from app.schemas.llm_usage import LlmUsageQueryParams
from app.services.llm_usage_read import LlmUsageReadService


class FakeControl:
    def __init__(self, cutover=False):
        self.ledger_cutover_enabled = cutover


class FakeControlRepo:
    def __init__(self, cutover=False):
        self._control = FakeControl(cutover)

    async def get_singleton(self):
        return self._control


class FakeReadRepo:
    def __init__(self, summary_row=None, breakdown_rows=None):
        self._summary = summary_row
        self._breakdown = breakdown_rows or []

    async def summary(self, params):
        return self._summary

    async def breakdown(self, params, column):
        return self._breakdown


class FakeAgent:
    def __init__(self, id, name):
        self.id = id
        self.name = name


class FakeAgentRepo:
    def __init__(self, agents=None):
        self._agents = agents or []

    async def get_by_ids(self, ids):
        return [a for a in self._agents if a.id in ids]


def _params():
    p = LlmUsageQueryParams.__new__(LlmUsageQueryParams)
    p.from_date = p.to_date = p.agent_id = p.group_id = p.provider = p.model = None
    return p


def _service(summary_row=None, breakdown_rows=None, cutover=False, agents=None):
    return LlmUsageReadService(
        FakeReadRepo(summary_row, breakdown_rows), FakeControlRepo(cutover), FakeAgentRepo(agents)
    )



@pytest.mark.asyncio
async def test_cost_per_conversation_divides_by_distinct():
    row = (Decimal("1.00"), 100, 100, 200, 4, 0, 200, Decimal("0.80"), Decimal("0.20"), 4)
    summ = await _service(summary_row=row).get_summary(_params())
    assert summ.total_cost_usd == 1.0
    assert summ.cost_per_conversation_usd == 0.20
    assert summ.non_conversation_cost_usd == 0.20
    assert summ.cost_is_partial is False
    assert summ.priced_token_coverage_pct == 100.0
    assert summ.cost_source == "daily_stats"


@pytest.mark.asyncio
async def test_partial_cost_and_token_coverage():
    row = (Decimal("0.50"), 50, 50, 100, 3, 1, 60, Decimal("0.50"), Decimal("0"), 2)
    summ = await _service(summary_row=row).get_summary(_params())
    assert summ.cost_is_partial is True
    assert summ.unpriced_calls == 1
    assert summ.priced_token_coverage_pct == 60.0
    assert summ.cost_per_conversation_usd == 0.25


@pytest.mark.asyncio
async def test_zero_conversations_yields_zero_per_conversation():
    row = (Decimal("0.10"), 10, 10, 20, 1, 0, 20, Decimal("0"), Decimal("0.10"), 0)
    summ = await _service(summary_row=row).get_summary(_params())
    assert summ.cost_per_conversation_usd == 0.0
    assert summ.non_conversation_cost_usd == 0.10


@pytest.mark.asyncio
async def test_cutover_on_reports_ledger_source():
    row = (Decimal("0"), 0, 0, 0, 0, 0, 0, Decimal("0"), Decimal("0"), 0)
    summ = await _service(summary_row=row, cutover=True).get_summary(_params())
    assert summ.cost_source == "llm_usage_ledger"


@pytest.mark.asyncio
async def test_empty_summary_when_scope_excludes_everything():
    summ = await _service(summary_row=None).get_summary(_params())
    assert summ.total_cost_usd == 0.0
    assert summ.total_calls == 0
    assert summ.priced_token_coverage_pct == 100.0
    assert summ.cost_source == "daily_stats"


@pytest.mark.asyncio
async def test_breakdown_provider_partial_flag():
    rows = [("openai", Decimal("0.30"), 0, 500, 3), ("anthropic", Decimal("0"), 1, 100, 1)]
    resp = await _service(breakdown_rows=rows).get_breakdown(_params(), "provider")
    by = {i.key: i for i in resp.items}
    assert by["openai"].cost_is_partial is False and by["openai"].calls == 3
    assert by["anthropic"].cost_is_partial is True and by["anthropic"].label == "anthropic"
    assert resp.dimension == "provider"


@pytest.mark.asyncio
async def test_breakdown_agent_resolves_names_and_unattributed():
    from uuid import uuid4

    aid = uuid4()
    rows = [(aid, Decimal("0.10"), 0, 100, 1), (None, Decimal("0.05"), 0, 50, 1)]
    resp = await _service(breakdown_rows=rows, agents=[FakeAgent(aid, "Sales Bot")]).get_breakdown(
        _params(), "agent"
    )
    by = {i.key: i for i in resp.items}
    assert by[str(aid)].label == "Sales Bot"
    assert by["unattributed"].label == "Unattributed"


@pytest.mark.asyncio
async def test_breakdown_source_relabels_workflow_and_analyst():
    rows = [("workflow", Decimal("0.80"), 0, 900, 5), ("llm_analyst", Decimal("0.20"), 0, 300, 4)]
    resp = await _service(breakdown_rows=rows).get_breakdown(_params(), "source")
    by = {i.key: i for i in resp.items}
    assert by["workflow"].label == "Workflow"
    assert by["llm_analyst"].label == "Analyst"
    assert resp.dimension == "source"
