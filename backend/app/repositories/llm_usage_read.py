from datetime import date, datetime, timedelta, timezone
from uuid import UUID

from injector import inject
from sqlalchemy import Date, cast, distinct, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.utils.analytics_agent_scope import resolve_scoped_agent_ids
from app.db.models.llm_usage import LlmUsageEventModel
from app.repositories.db_repository import DbRepository

_COST = LlmUsageEventModel.cost_usd
_CONV = LlmUsageEventModel.conversation_id
_TOKENS = LlmUsageEventModel.total_tokens


def _day_start(d: date) -> datetime:
    return datetime(d.year, d.month, d.day, tzinfo=timezone.utc)


def _utc_day(column):
    """Truncate a tz-aware timestamp to its UTC calendar day"""
    return cast(func.timezone("UTC", column), Date)


@inject
class LlmUsageReadRepository(DbRepository[LlmUsageEventModel]):
    """Aggregate reads over the ``llm_usage_events`` ledger for the LLM Usage surfaces"""

    def __init__(self, db: AsyncSession):
        super().__init__(LlmUsageEventModel, db)

    async def _scope_conditions(self, params) -> list | None:
        """Build the shared WHERE list, or ``None`` when the scope resolves to no agents"""
        agent_ids = await resolve_scoped_agent_ids(self.db, params.agent_id, params.group_id)
        conds = []
        if agent_ids is not None:
            if not agent_ids:
                return None
            conds.append(
                LlmUsageEventModel.agent_id == agent_ids[0]
                if len(agent_ids) == 1
                else LlmUsageEventModel.agent_id.in_(agent_ids)
            )
        if params.from_date is not None:
            conds.append(LlmUsageEventModel.occurred_at >= _day_start(params.from_date))
        if params.to_date is not None:
            conds.append(LlmUsageEventModel.occurred_at < _day_start(params.to_date) + timedelta(days=1))
        if params.provider:
            conds.append(LlmUsageEventModel.provider_key == params.provider.strip().lower())
        if params.model:
            conds.append(LlmUsageEventModel.model_key == params.model.strip().lower())
        return conds

    async def summary(self, params):
        conds = await self._scope_conditions(params)
        if conds is None:
            return None
        stmt = select(
            func.coalesce(func.sum(_COST), 0),
            func.coalesce(func.sum(LlmUsageEventModel.input_tokens), 0),
            func.coalesce(func.sum(LlmUsageEventModel.output_tokens), 0),
            func.coalesce(func.sum(_TOKENS), 0),
            func.count(),
            func.count().filter(_COST.is_(None)),
            func.coalesce(func.sum(_TOKENS).filter(_COST.isnot(None)), 0),
            func.coalesce(func.sum(_COST).filter(_CONV.isnot(None)), 0),
            func.coalesce(func.sum(_COST).filter(_CONV.is_(None)), 0),
            func.count(distinct(_CONV)),
        ).where(*conds)
        return (await self.db.execute(stmt)).one()

    async def timeseries(self, params):
        conds = await self._scope_conditions(params)
        if conds is None:
            return []
        day = _utc_day(LlmUsageEventModel.occurred_at)
        stmt = (
            select(
                day.label("stat_date"),
                func.coalesce(func.sum(_COST), 0),
                func.coalesce(func.sum(_TOKENS), 0),
                func.count(),
                func.count().filter(_COST.is_(None)),
            )
            .where(*conds)
            .group_by(day)
            .order_by(day)
        )
        return list((await self.db.execute(stmt)).all())

    async def breakdown(self, params, key_column):
        conds = await self._scope_conditions(params)
        if conds is None:
            return []
        stmt = (
            select(
                key_column.label("key"),
                func.coalesce(func.sum(_COST), 0),
                func.count().filter(_COST.is_(None)),
                func.coalesce(func.sum(_TOKENS), 0),
                func.count(),
            )
            .where(*conds)
            .group_by(key_column)
            .order_by(func.coalesce(func.sum(_COST), 0).desc())
        )
        return list((await self.db.execute(stmt)).all())

    async def distinct_values(self, params, column) -> list[str]:
        conds = await self._scope_conditions(params)
        if conds is None:
            return []
        stmt = select(distinct(column)).where(*conds, column.isnot(None)).order_by(column)
        return [row[0] for row in (await self.db.execute(stmt)).all()]

    async def distinct_agent_ids(self, params) -> list[UUID]:
        conds = await self._scope_conditions(params)
        if conds is None:
            return []
        col = LlmUsageEventModel.agent_id
        stmt = select(distinct(col)).where(*conds, col.isnot(None))
        return [row[0] for row in (await self.db.execute(stmt)).all()]
