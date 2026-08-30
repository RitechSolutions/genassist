from datetime import date, datetime, timedelta, timezone
from uuid import UUID

from injector import inject
from sqlalchemy import Date, cast, distinct, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config.llm_pricing import PricingStatus
from app.core.utils.analytics_agent_scope import resolve_authorized_agent_ids
from app.db.models.llm_usage import LlmUsageEventModel
from app.repositories.db_repository import DbRepository

_COST = LlmUsageEventModel.cost_usd
_CONV = LlmUsageEventModel.conversation_id
_STATUS = LlmUsageEventModel.pricing_status
_SOURCE = LlmUsageEventModel.source
_CACHE_READ = LlmUsageEventModel.cache_read_tokens
_CACHE_WRITE = LlmUsageEventModel.cache_creation_tokens
# Normalized at write time, so reads never reapply per-provider reporting rules
_PROMPT_TOKENS = LlmUsageEventModel.prompt_tokens
_TOKENS = func.greatest(LlmUsageEventModel.total_tokens, _PROMPT_TOKENS + LlmUsageEventModel.output_tokens)

AGENT_STUDIO_TEST_SOURCES = ("workflow_test", "node_test")


def _day_start(d: date) -> datetime:
    return datetime(d.year, d.month, d.day, tzinfo=timezone.utc)


def _utc_day(column):
    """Truncate a tz-aware timestamp to its UTC calendar day"""
    return cast(func.timezone("UTC", column), Date)


def _calls_with_status(status: PricingStatus):
    return func.count().filter(_STATUS == status.value)


@inject
class LlmUsageReadRepository(DbRepository[LlmUsageEventModel]):
    """Aggregate reads over the ``llm_usage_events`` ledger for the LLM Usage surfaces"""

    def __init__(self, db: AsyncSession):
        super().__init__(LlmUsageEventModel, db)

    async def resolve_scope(self, params) -> list[UUID] | None:
        return await resolve_authorized_agent_ids(self.db, params.agent_id, params.group_id)

    @staticmethod
    def _conditions(params, scope: list[UUID] | None, *, use_provider: bool = True, use_model: bool = True) -> list:
        """Shared filter conditions for usage queries"""
        conds = [LlmUsageEventModel.is_deleted == 0]
        if scope is not None:
            conds.append(
                LlmUsageEventModel.agent_id == scope[0] if len(scope) == 1 else LlmUsageEventModel.agent_id.in_(scope)
            )
        if params.from_date is not None:
            conds.append(LlmUsageEventModel.occurred_at >= _day_start(params.from_date))
        if params.to_date is not None:
            conds.append(LlmUsageEventModel.occurred_at < _day_start(params.to_date) + timedelta(days=1))
        if use_provider and params.provider:
            conds.append(LlmUsageEventModel.provider_key == params.provider.strip().lower())
        if use_model and params.model:
            conds.append(LlmUsageEventModel.model_key == params.model.strip().lower())
        return conds

    async def summary(self, params, scope: list[UUID] | None):
        stmt = select(
            func.coalesce(func.sum(_COST), 0).label("sum_cost"),
            func.coalesce(func.sum(_PROMPT_TOKENS), 0).label("input_tokens"),
            func.coalesce(func.sum(LlmUsageEventModel.output_tokens), 0).label("output_tokens"),
            func.coalesce(func.sum(_TOKENS), 0).label("total_tokens"),
            func.count().label("total_calls"),
            func.count().filter(_COST.is_(None)).label("unpriced_calls"),
            _calls_with_status(PricingStatus.CONFIGURED).label("configured_calls"),
            _calls_with_status(PricingStatus.FALLBACK).label("fallback_calls"),
            _calls_with_status(PricingStatus.LEGACY_ESTIMATE).label("legacy_estimate_calls"),
            func.coalesce(func.sum(_TOKENS).filter(_COST.isnot(None)), 0).label("priced_tokens"),
            func.coalesce(func.sum(_COST).filter(_CONV.isnot(None)), 0).label("conversation_cost"),
            func.coalesce(func.sum(_COST).filter(_SOURCE.in_(AGENT_STUDIO_TEST_SOURCES)), 0).label(
                "agent_studio_test_cost"
            ),
            func.count(distinct(_CONV)).label("distinct_conversations"),
            func.coalesce(func.sum(_CACHE_READ), 0).label("cache_read_tokens"),
            func.coalesce(func.sum(_CACHE_WRITE), 0).label("cache_creation_tokens"),
        ).where(*self._conditions(params, scope))
        return (await self.db.execute(stmt)).mappings().one()

    async def last_unpriced_at(self) -> datetime | None:
        """Return when the tenant last recorded an unpriced call, ignoring read filters"""
        stmt = select(func.max(LlmUsageEventModel.created_at)).where(
            LlmUsageEventModel.is_deleted == 0, _COST.is_(None)
        )
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def timeseries(self, params, scope: list[UUID] | None):
        day = _utc_day(LlmUsageEventModel.occurred_at)
        stmt = (
            select(
                day.label("stat_date"),
                func.coalesce(func.sum(_COST), 0),
                func.coalesce(func.sum(_TOKENS), 0),
                func.count(),
                func.count().filter(_COST.is_(None)),
            )
            .where(*self._conditions(params, scope))
            .group_by(day)
            .order_by(day)
        )
        return list((await self.db.execute(stmt)).all())

    async def breakdown(self, params, scope: list[UUID] | None, key_column, extra_conditions=None):
        stmt = (
            select(
                key_column.label("key"),
                func.coalesce(func.sum(_COST), 0),
                func.count().filter(_COST.is_(None)),
                func.coalesce(func.sum(_TOKENS), 0),
                func.count(),
            )
            .where(*self._conditions(params, scope), *(extra_conditions or ()))
            .group_by(key_column)
            .order_by(func.coalesce(func.sum(_COST), 0).desc())
        )
        return list((await self.db.execute(stmt)).all())

    async def distinct_values(
        self, params, scope: list[UUID] | None, column, *, use_provider: bool = True, use_model: bool = True
    ) -> list[str]:
        conds = self._conditions(params, scope, use_provider=use_provider, use_model=use_model)
        stmt = select(distinct(column)).where(*conds, column.isnot(None)).order_by(column)
        return [row[0] for row in (await self.db.execute(stmt)).all()]

    async def distinct_agent_ids(self, params, scope: list[UUID] | None) -> list[UUID]:
        col = LlmUsageEventModel.agent_id
        stmt = select(distinct(col)).where(*self._conditions(params, scope), col.isnot(None))
        return [row[0] for row in (await self.db.execute(stmt)).all()]

    async def distinct_agent_workflow_pairs(self, params, scope: list[UUID] | None, extra_conditions=None):
        stmt = (
            select(LlmUsageEventModel.agent_id, LlmUsageEventModel.workflow_id)
            .distinct()
            .where(*self._conditions(params, scope), *(extra_conditions or ()))
        )
        return list((await self.db.execute(stmt)).all())
