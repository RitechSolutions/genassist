from collections import defaultdict
from datetime import datetime, timezone

from injector import inject
from sqlalchemy import func

from app.db.models.llm_usage import LlmUsageEventModel
from app.repositories.agent import AgentRepository
from app.repositories.llm_usage_read import LlmUsageReadRepository
from app.repositories.workflow import WorkflowRepository
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
    "llm": func.concat_ws(
        " · ",
        func.coalesce(LlmUsageEventModel.provider_key, "unknown"),
        func.coalesce(LlmUsageEventModel.model_key, "unknown"),
    ),
    "evaluation_method": LlmUsageEventModel.purpose,
    "node": LlmUsageEventModel.node_id,
}

_EXTRA_BREAKDOWN_CONDITIONS = {
    "llm": (LlmUsageEventModel.source_type == "workflow",),
    "evaluation_method": (LlmUsageEventModel.source_type == "evaluation",),
    "node": (LlmUsageEventModel.source_type == "workflow",),
}

_SOURCE_LABELS = {"workflow": "Workflow", "llm_analyst": "Conversation Analyst", "evaluation": "Evaluations"}

_EVALUATION_METHOD_LABELS = {"llm_judge": "LLM Judge", "provenance_judge": "Provenance"}

_EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)

_NODE_ID_LIMIT = 128


def _is_empty_scope(scope) -> bool:
    """True when the filter resolved to “no agents”"""
    return scope is not None and not scope


def _node_removed(key, node_names: dict, current_nodes: set) -> bool | None:
    if not key:
        return None
    if key in current_nodes:
        return False
    return True if key in node_names else None


def _disambiguate_labels(items) -> None:
    """Suffix duplicate node names with the shortest distinguishing id prefix"""
    groups = defaultdict(list)
    for item in items:
        if item.key != "unattributed":
            groups[item.label].append(item)
    for label, dupes in groups.items():
        if len(dupes) < 2:
            continue
        width, longest = 6, max(len(d.key) for d in dupes)
        while len({d.key[:width] for d in dupes}) < len(dupes) and width < longest:
            width += 1
        for dupe in dupes:
            dupe.label = f"{label} · {dupe.key[:width]}"


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
        workflow_repo: WorkflowRepository,
    ):
        self.repo = repo
        self.agent_repo = agent_repo
        self.workflow_repo = workflow_repo

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
        total_calls = int(row["total_calls"])
        total_tokens = int(row["total_tokens"])
        unpriced_calls = int(row["unpriced_calls"])
        distinct_conversations = row["distinct_conversations"]
        return LlmUsageSummaryResponse(
            from_date=params.from_date,
            to_date=params.to_date,
            total_cost_usd=float(row["sum_cost"]),
            cost_is_partial=unpriced_calls > 0,
            cost_per_conversation_usd=(
                float(row["conversation_cost"]) / distinct_conversations if distinct_conversations else None
            ),
            agent_studio_test_cost_usd=float(row["agent_studio_test_cost"]),
            total_input_tokens=int(row["input_tokens"]),
            total_output_tokens=int(row["output_tokens"]),
            total_tokens=total_tokens,
            total_cache_read_tokens=int(row["cache_read_tokens"]),
            total_cache_creation_tokens=int(row["cache_creation_tokens"]),
            total_calls=total_calls,
            configured_calls=int(row["configured_calls"]),
            fallback_calls=int(row["fallback_calls"]),
            legacy_estimate_calls=int(row["legacy_estimate_calls"]),
            unpriced_calls=unpriced_calls,
            priced_token_coverage_pct=_coverage_pct(
                total_calls, total_tokens, int(row["priced_tokens"]), unpriced_calls
            ),
            last_unpriced_at=(await self.repo.last_unpriced_at() if unpriced_calls else None),
        )

    async def _breakdown(self, params, scope, dimension: str) -> LlmUsageBreakdownResponse:
        rows = (
            []
            if _is_empty_scope(scope)
            else await self.repo.breakdown(
                params,
                scope,
                _DIMENSION_COLUMNS[dimension],
                _EXTRA_BREAKDOWN_CONDITIONS.get(dimension),
            )
        )
        agent_names = await self._agent_names([k for k, *_ in rows]) if dimension == "agent" else {}
        node_names, current_nodes = (
            await self._node_labels(params, scope) if dimension == "node" and rows else ({}, set())
        )
        items = [self._breakdown_item(dimension, row, agent_names, node_names, current_nodes) for row in rows]
        if dimension == "node":
            _disambiguate_labels(items)
        return LlmUsageBreakdownResponse(dimension=dimension, items=items, total=len(items))

    async def _agent_names(self, agent_ids) -> dict:
        ids = [a for a in agent_ids if a is not None]
        if not ids:
            return {}
        rows = await self.agent_repo.get_by_ids(ids)
        return {a.id: a.name for a in rows}

    async def _node_labels(self, params, scope) -> tuple[dict, set]:
        """Node id -> display name, plus the ids still present in the agents' current workflows"""
        pairs = await self.repo.distinct_agent_workflow_pairs(params, scope, _EXTRA_BREAKDOWN_CONDITIONS["node"])
        agent_ids = [a for a, _ in pairs if a is not None]
        agents = await self.agent_repo.get_by_ids(agent_ids) if agent_ids else []
        current_ids = {a.workflow_id for a in agents if a.workflow_id is not None}
        workflow_ids = list({w for _, w in pairs if w is not None} | current_ids)
        if not workflow_ids:
            return {}, set()
        workflows = await self.workflow_repo.get_by_ids(workflow_ids)
        names: dict = {}
        current_nodes: set = set()
        for workflow in sorted(workflows, key=lambda w: (w.id in current_ids, w.created_at or _EPOCH, str(w.id))):
            is_current = workflow.id in current_ids
            for node in workflow.nodes or []:
                if not isinstance(node, dict) or not node.get("id"):
                    continue
                key = str(node["id"])[:_NODE_ID_LIMIT]
                data = node.get("data")
                name = data.get("name") if isinstance(data, dict) else None
                if isinstance(name, str) and name:
                    names[key] = name
                if is_current:
                    current_nodes.add(key)
        return names, current_nodes

    @staticmethod
    def _breakdown_item(
        dimension: str, row, agent_names: dict, node_names: dict, current_nodes: set
    ) -> LlmUsageBreakdownItem:
        key, cost, unpriced, tokens, calls = row
        removed = None
        if dimension == "agent":
            label = agent_names.get(key, "Unattributed" if key is None else "Unknown")
            key_str = str(key) if key is not None else "unattributed"
        elif dimension == "node":
            key_str = key or "unattributed"
            label = "Unattributed" if not key else node_names.get(key) or "Unknown"
            removed = _node_removed(key, node_names, current_nodes)
        elif dimension == "source":
            key_str = key or "unknown"
            label = _SOURCE_LABELS.get(key, key or "Unknown")
        elif dimension == "evaluation_method":
            key_str = key or "unknown"
            label = _EVALUATION_METHOD_LABELS.get(key, key or "Unknown")
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
            removed=removed,
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
