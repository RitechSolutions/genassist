from decimal import Decimal
from typing import Any, Optional
from uuid import UUID

from injector import inject
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.events.group_scope import GROUP_SCOPE_BYPASS_FLAG
from app.db.models.agent import AgentModel
from app.db.models.agent_response_log import AgentResponseLogModel
from app.db.models.conversation import ConversationModel
from app.db.models.llm_usage import LlmUsageEventModel
from app.db.models.operator import OperatorModel
from app.repositories.db_repository import DbRepository

# Fields a forced re-run overwrites on an existing legacy row; identity columns stay put.
# Includes attribution so a re-run restamps rows backfilled before the agent fix.
_FORCE_UPDATE_COLUMNS = (
    "input_tokens",
    "prompt_tokens",
    "output_tokens",
    "total_tokens",
    "cost_usd",
    "pricing_status",
    "agent_id",
    "workflow_id",
    "conversation_id",
    "occurred_at",
)


@inject
class LlmUsageBackfillRepository(DbRepository[LlmUsageEventModel]):
    """Reads pre-activation agent_response_logs and writes their aggregate ledger events"""

    def __init__(self, db: AsyncSession):
        super().__init__(LlmUsageEventModel, db)

    async def fetch_log_page(self, boundary, after_id: Optional[UUID], limit: int) -> list[Any]:
        """One keyset page of logs older than ``boundary``, oldest id first"""
        stmt = select(
            AgentResponseLogModel.id,
            AgentResponseLogModel.conversation_id,
            AgentResponseLogModel.logged_at,
            AgentResponseLogModel.input_tokens,
            AgentResponseLogModel.output_tokens,
            AgentResponseLogModel.total_tokens,
            AgentResponseLogModel.cost_usd,
        ).where(
            AgentResponseLogModel.logged_at < boundary,
            AgentResponseLogModel.is_deleted == 0,
        )
        if after_id is not None:
            stmt = stmt.where(AgentResponseLogModel.id > after_id)
        stmt = stmt.order_by(AgentResponseLogModel.id.asc()).limit(limit)
        result = await self.db.execute(stmt)
        return list(result.all())

    async def fetch_raw_responses(self, ids: list[UUID]) -> dict[UUID, str]:
        if not ids:
            return {}
        result = await self.db.execute(
            select(AgentResponseLogModel.id, AgentResponseLogModel.raw_response).where(
                AgentResponseLogModel.id.in_(ids)
            )
        )
        return {row[0]: row[1] for row in result.all()}

    async def existing_conversation_ids(self, ids: set[UUID]) -> set[UUID]:
        """Present conversation ids; absent ones are NULLed on the event, row kept."""
        ids = {i for i in ids if i is not None}
        if not ids:
            return set()
        stmt = (
            select(ConversationModel.id)
            .where(ConversationModel.id.in_(ids))
            .execution_options(**{GROUP_SCOPE_BYPASS_FLAG: True})
        )
        result = await self.db.execute(stmt)
        return {row[0] for row in result.all()}

    async def resolve_agent_workflow(
        self, conversation_ids: set[UUID]
    ) -> dict[UUID, tuple[Optional[UUID], Optional[UUID]]]:
        """Map each conversation to its (agent_id, workflow_id)"""
        conversation_ids = {c for c in conversation_ids if c is not None}
        if not conversation_ids:
            return {}
        result = await self.db.execute(
            select(ConversationModel.id, AgentModel.id, AgentModel.workflow_id)
            .join(OperatorModel, ConversationModel.operator_id == OperatorModel.id)
            .join(AgentModel, AgentModel.operator_id == OperatorModel.id)
            .where(ConversationModel.id.in_(conversation_ids))
            .execution_options(**{GROUP_SCOPE_BYPASS_FLAG: True})
        )
        return {row[0]: (row[1], row[2]) for row in result.all()}

    async def insert_events(self, rows: list[dict], force: bool) -> int:
        if not rows:
            return 0
        stmt = insert(LlmUsageEventModel).values(rows)
        if force:
            stmt = stmt.on_conflict_do_update(
                constraint="uq_llm_usage_events_execution_call",
                set_={col: getattr(stmt.excluded, col) for col in _FORCE_UPDATE_COLUMNS},
            )
        else:
            stmt = stmt.on_conflict_do_nothing(constraint="uq_llm_usage_events_execution_call")
        result = await self.db.execute(stmt)
        await self.db.flush()
        return result.rowcount or 0

    async def legacy_event_aggregates(self) -> tuple[int, int, int, int, Decimal]:
        result = await self.db.execute(
            select(
                func.count(),
                func.coalesce(func.sum(LlmUsageEventModel.input_tokens), 0),
                func.coalesce(func.sum(LlmUsageEventModel.output_tokens), 0),
                func.coalesce(func.sum(LlmUsageEventModel.total_tokens), 0),
                func.coalesce(func.sum(LlmUsageEventModel.cost_usd), 0),
            )
            .select_from(LlmUsageEventModel)
            .where(LlmUsageEventModel.legacy_response_log_id.isnot(None))
        )
        row = result.one()
        return int(row[0]), int(row[1]), int(row[2]), int(row[3]), Decimal(row[4])
