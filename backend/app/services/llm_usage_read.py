from injector import inject

from app.db.models.llm_usage import LlmUsageEventModel
from app.repositories.agent import AgentRepository
from app.repositories.llm_usage_control import LlmUsageControlRepository
from app.repositories.llm_usage_read import LlmUsageReadRepository
from app.schemas.llm_usage import (
    LlmUsageAgentOption,
    LlmUsageBreakdownItem,
    LlmUsageBreakdownResponse,
    LlmUsageFilterOptionsResponse,
    LlmUsageQueryParams,
    LlmUsageSummaryResponse,
    LlmUsageTimeseriesItem,
    LlmUsageTimeseriesResponse,
)
from app.schemas.llm_usage_control import COST_SOURCE_DAILY_STATS, COST_SOURCE_LEDGER

_DIMENSION_COLUMNS = {
    "provider": LlmUsageEventModel.provider_key,
    "model": LlmUsageEventModel.model_key,
    "agent": LlmUsageEventModel.agent_id,
}


@inject
class LlmUsageReadService:
    """Reads the LLM usage ledger and applies the cost/coverage math"""

    def __init__(
        self,
        repo: LlmUsageReadRepository,
        control_repo: LlmUsageControlRepository,
        agent_repo: AgentRepository,
    ):
        self.repo = repo
        self.control_repo = control_repo
        self.agent_repo = agent_repo

    async def _cost_source(self) -> str:
        control = await self.control_repo.get_singleton()
        if control is not None and control.ledger_cutover_enabled:
            return COST_SOURCE_LEDGER
        return COST_SOURCE_DAILY_STATS

    async def get_summary(self, params: LlmUsageQueryParams) -> LlmUsageSummaryResponse:
        cost_source = await self._cost_source()
        row = await self.repo.summary(params)
        if row is None:
            return self._empty_summary(params, cost_source)
        (
            sum_cost,
            input_tokens,
            output_tokens,
            total_tokens,
            total_calls,
            unpriced_calls,
            priced_tokens,
            conversation_cost,
            non_conversation_cost,
            distinct_conversations,
        ) = row
        coverage = 100.0 if not total_tokens else round(float(priced_tokens) / float(total_tokens) * 100, 4)
        per_conversation = float(conversation_cost) / distinct_conversations if distinct_conversations else 0.0
        return LlmUsageSummaryResponse(
            from_date=params.from_date,
            to_date=params.to_date,
            total_cost_usd=float(sum_cost),
            cost_is_partial=unpriced_calls > 0,
            cost_per_conversation_usd=per_conversation,
            non_conversation_cost_usd=float(non_conversation_cost),
            total_input_tokens=int(input_tokens),
            total_output_tokens=int(output_tokens),
            total_tokens=int(total_tokens),
            total_calls=int(total_calls),
            unpriced_calls=int(unpriced_calls),
            priced_token_coverage_pct=coverage,
            cost_source=cost_source,
        )

    async def get_timeseries(self, params: LlmUsageQueryParams) -> LlmUsageTimeseriesResponse:
        cost_source = await self._cost_source()
        rows = await self.repo.timeseries(params)
        items = [
            LlmUsageTimeseriesItem(
                stat_date=stat_date,
                cost_usd=float(cost),
                total_tokens=int(tokens),
                calls=int(calls),
                unpriced_calls=int(unpriced),
            )
            for stat_date, cost, tokens, calls, unpriced in rows
        ]
        return LlmUsageTimeseriesResponse(items=items, total=len(items), cost_source=cost_source)

    async def get_breakdown(self, params: LlmUsageQueryParams, dimension: str) -> LlmUsageBreakdownResponse:
        cost_source = await self._cost_source()
        rows = await self.repo.breakdown(params, _DIMENSION_COLUMNS[dimension])
        agent_names = await self._agent_names([k for k, *_ in rows]) if dimension == "agent" else {}
        items = [self._breakdown_item(dimension, row, agent_names) for row in rows]
        return LlmUsageBreakdownResponse(
            dimension=dimension, items=items, total=len(items), cost_source=cost_source
        )

    async def get_filter_options(self, params: LlmUsageQueryParams) -> LlmUsageFilterOptionsResponse:
        providers = await self.repo.distinct_values(params, LlmUsageEventModel.provider_key)
        models = await self.repo.distinct_values(params, LlmUsageEventModel.model_key)
        agent_ids = await self.repo.distinct_agent_ids(params)
        names = await self._agent_names(agent_ids)
        agents = [LlmUsageAgentOption(id=aid, name=names.get(aid, "Unknown")) for aid in agent_ids]
        agents.sort(key=lambda a: a.name.lower())
        return LlmUsageFilterOptionsResponse(providers=providers, models=models, agents=agents)

    async def _agent_names(self, agent_ids) -> dict:
        ids = [a for a in agent_ids if a is not None]
        if not ids:
            return {}
        rows = await self.agent_repo.get_by_ids(ids)
        return {a.id: a.name for a in rows}

    @staticmethod
    def _breakdown_item(dimension: str, row, agent_names: dict) -> LlmUsageBreakdownItem:
        key, cost, unpriced, tokens, calls = row
        if dimension == "agent":
            label = agent_names.get(key, "Unattributed" if key is None else "Unknown")
            key_str = str(key) if key is not None else "unattributed"
        else:
            key_str = key or "unknown"
            label = key or "Unknown"
        return LlmUsageBreakdownItem(
            key=key_str,
            label=label,
            cost_usd=float(cost),
            cost_is_partial=int(unpriced) > 0,
            total_tokens=int(tokens),
            calls=int(calls),
            unpriced_calls=int(unpriced),
        )

    @staticmethod
    def _empty_summary(params: LlmUsageQueryParams, cost_source: str) -> LlmUsageSummaryResponse:
        return LlmUsageSummaryResponse(
            from_date=params.from_date,
            to_date=params.to_date,
            total_cost_usd=0.0,
            cost_is_partial=False,
            cost_per_conversation_usd=0.0,
            non_conversation_cost_usd=0.0,
            total_input_tokens=0,
            total_output_tokens=0,
            total_tokens=0,
            total_calls=0,
            unpriced_calls=0,
            priced_token_coverage_pct=100.0,
            cost_source=cost_source,
        )
