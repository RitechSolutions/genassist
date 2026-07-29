from injector import inject

from app.db.models.llm_usage import LlmUsageEventModel
from app.repositories.agent import AgentRepository
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

_DIMENSION_COLUMNS = {
    "provider": LlmUsageEventModel.provider_key,
    "model": LlmUsageEventModel.model_key,
    "agent": LlmUsageEventModel.agent_id,
    "source": LlmUsageEventModel.source_type,
}

_SOURCE_LABELS = {"workflow": "Workflow", "llm_analyst": "Conversation Analyst"}


def _is_empty_scope(scope) -> bool:
    """True when the filter resolved to “no agents”"""
    return scope is not None and not scope


def _coverage_pct(total_calls: int, total_tokens: int, priced_tokens: int, unpriced_calls: int) -> float:
    """Percent of tokens that had a price"""
    if not total_calls:
        return 100.0
    if total_tokens:
        return round(priced_tokens / total_tokens * 100, 4)
    if not unpriced_calls:
        return 100.0
    return round((total_calls - unpriced_calls) / total_calls * 100, 4)


@inject
class LlmUsageReadService:
    """Reads the LLM usage ledger and applies the cost/coverage math"""

    def __init__(
        self,
        repo: LlmUsageReadRepository,
        agent_repo: AgentRepository,
    ):
        self.repo = repo
        self.agent_repo = agent_repo

    async def get_summary(self, params: LlmUsageQueryParams) -> LlmUsageSummaryResponse:
        scope = await self.repo.resolve_scope(params)
        return await self._summary(params, scope)

    async def get_timeseries(self, params: LlmUsageQueryParams) -> LlmUsageTimeseriesResponse:
        scope = await self.repo.resolve_scope(params)
        rows = [] if _is_empty_scope(scope) else await self.repo.timeseries(params, scope)
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
        return LlmUsageTimeseriesResponse(items=items, total=len(items))

    async def get_breakdown(self, params: LlmUsageQueryParams, dimension: str) -> LlmUsageBreakdownResponse:
        scope = await self.repo.resolve_scope(params)
        return await self._breakdown(params, scope, dimension)

    async def get_export_report(
        self, params: LlmUsageQueryParams, dimension: str
    ) -> tuple[LlmUsageSummaryResponse, LlmUsageBreakdownResponse]:
        """Summary plus breakdown for one export"""
        scope = await self.repo.resolve_scope(params)
        return (
            await self._summary(params, scope),
            await self._breakdown(params, scope, dimension),
        )

    async def get_filter_options(self, params: LlmUsageQueryParams) -> LlmUsageFilterOptionsResponse:
        scope = await self.repo.resolve_scope(params)
        if _is_empty_scope(scope):
            return LlmUsageFilterOptionsResponse(providers=[], models=[], agents=[])
        providers = await self.repo.distinct_values(
            params, scope, LlmUsageEventModel.provider_key, use_provider=False, use_model=False
        )
        models = await self.repo.distinct_values(params, scope, LlmUsageEventModel.model_key, use_model=False)
        agent_ids = await self.repo.distinct_agent_ids(params, scope)
        names = await self._agent_names(agent_ids)
        agents = [LlmUsageAgentOption(id=aid, name=names.get(aid, "Unknown")) for aid in agent_ids]
        agents.sort(key=lambda a: a.name.lower())
        return LlmUsageFilterOptionsResponse(providers=providers, models=models, agents=agents)

    async def _summary(self, params, scope) -> LlmUsageSummaryResponse:
        row = None if _is_empty_scope(scope) else await self.repo.summary(params, scope)
        if row is None:
            return self._empty_summary(params)
        (
            sum_cost,
            input_tokens,
            output_tokens,
            total_tokens,
            total_calls,
            unpriced_calls,
            configured_calls,
            fallback_calls,
            legacy_estimate_calls,
            priced_tokens,
            conversation_cost,
            agent_studio_test_cost,
            distinct_conversations,
        ) = row
        return LlmUsageSummaryResponse(
            from_date=params.from_date,
            to_date=params.to_date,
            total_cost_usd=float(sum_cost),
            cost_is_partial=unpriced_calls > 0,
            cost_per_conversation_usd=(
                float(conversation_cost) / distinct_conversations if distinct_conversations else None
            ),
            agent_studio_test_cost_usd=float(agent_studio_test_cost),
            total_input_tokens=int(input_tokens),
            total_output_tokens=int(output_tokens),
            total_tokens=int(total_tokens),
            total_calls=int(total_calls),
            configured_calls=int(configured_calls),
            fallback_calls=int(fallback_calls),
            legacy_estimate_calls=int(legacy_estimate_calls),
            unpriced_calls=int(unpriced_calls),
            priced_token_coverage_pct=_coverage_pct(
                int(total_calls), int(total_tokens), int(priced_tokens), int(unpriced_calls)
            ),
        )

    async def _breakdown(self, params, scope, dimension: str) -> LlmUsageBreakdownResponse:
        rows = [] if _is_empty_scope(scope) else await self.repo.breakdown(params, scope, _DIMENSION_COLUMNS[dimension])
        agent_names = await self._agent_names([k for k, *_ in rows]) if dimension == "agent" else {}
        items = [self._breakdown_item(dimension, row, agent_names) for row in rows]
        return LlmUsageBreakdownResponse(dimension=dimension, items=items, total=len(items))

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
        elif dimension == "source":
            key_str = key or "unknown"
            label = _SOURCE_LABELS.get(key, key or "Unknown")
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
    def _empty_summary(params: LlmUsageQueryParams) -> LlmUsageSummaryResponse:
        return LlmUsageSummaryResponse(
            from_date=params.from_date,
            to_date=params.to_date,
            total_cost_usd=0.0,
            cost_is_partial=False,
            cost_per_conversation_usd=None,
            agent_studio_test_cost_usd=0.0,
            total_input_tokens=0,
            total_output_tokens=0,
            total_tokens=0,
            total_calls=0,
            configured_calls=0,
            fallback_calls=0,
            legacy_estimate_calls=0,
            unpriced_calls=0,
            priced_token_coverage_pct=100.0,
        )
