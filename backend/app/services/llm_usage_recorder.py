import logging
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Optional
from uuid import UUID

from sqlalchemy import exists, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config.llm_pricing import PricingStatus, find_pricing_with_status
from app.core.utils.date_time_utils import utc_now
from app.core.utils.db_connection_utils import create_tenant_request_scope
from app.db.models.agent import AgentModel
from app.db.models.conversation import ConversationModel
from app.db.models.llm import LlmAnalystModel, LlmProvidersModel
from app.db.models.llm_usage import (
    CONTROL_SINGLETON_KEY,
    LlmUsageCaptureRunModel,
    LlmUsageControlModel,
    LlmUsageEventModel,
)
from app.db.models.workflow import WorkflowModel
from app.dependencies.injector import injector

logger = logging.getLogger(__name__)


@dataclass
class WorkflowUsageContext:
    """Attribution for a top-level workflow run's recorded usage"""

    source: str
    agent_id: Optional[UUID] = None
    workflow_id: Optional[UUID] = None
    conversation_id: Optional[UUID] = None
    source_type: str = "workflow"
    extra: dict[str, Any] = field(default_factory=dict)


def _normalize(value: Optional[str], limit: int) -> Optional[str]:
    if not value:
        return None
    return str(value).lower().strip()[:limit] or None


def _coerce_uuid(value: Any) -> Optional[UUID]:
    if value is None or isinstance(value, UUID):
        return value
    try:
        return UUID(str(value))
    except (ValueError, AttributeError, TypeError):
        return None


def _resolve_cost(provider: str, model: str, input_tokens: int, output_tokens: int) -> dict[str, Any]:
    """Snapshot the rate + cost for one call. Unpriced → NULL cost"""
    resolution = find_pricing_with_status(provider, model)
    if resolution.status is PricingStatus.UNPRICED:
        return {
            "input_per_1k": None,
            "output_per_1k": None,
            "cost_usd": None,
            "pricing_status": PricingStatus.UNPRICED.value,
        }
    thousand = Decimal(1000)
    cost = (Decimal(int(input_tokens)) / thousand) * resolution.input_per_1k + (
        Decimal(int(output_tokens)) / thousand
    ) * resolution.output_per_1k
    return {
        "input_per_1k": resolution.input_per_1k,
        "output_per_1k": resolution.output_per_1k,
        "cost_usd": cost,
        "pricing_status": resolution.status.value,
    }


class LlmUsageRecorder:
    """Isolated, always-safe writer. Each public method manages its own request scope"""

    async def _capture_enabled(self, session: AsyncSession) -> bool:
        """Read the control singleton first. Absent or off → recorder stays inert."""
        result = await session.execute(
            select(LlmUsageControlModel.capture_enabled).where(
                LlmUsageControlModel.singleton_key == CONTROL_SINGLETON_KEY
            )
        )
        return bool(result.scalar_one_or_none())

    async def _existing_ids(self, session: AsyncSession, model, ids: set[UUID]) -> set[UUID]:
        """One SELECT per FK type; ids not present come back absent so callers NULL them."""
        ids = {i for i in ids if i is not None}
        if not ids:
            return set()
        result = await session.execute(select(model.id).where(model.id.in_(ids)))
        return {row[0] for row in result.all()}

    async def record_workflow_state(
        self,
        state,
        usage_context: WorkflowUsageContext,
        execution_outcome: str,
    ) -> None:
        try:
            async with create_tenant_request_scope():
                session = injector.get(AsyncSession)
                try:
                    if not await self._capture_enabled(session):
                        return

                    entries = list(getattr(state, "llm_usage", []) or [])
                    occurred_at = utc_now()
                    conversation_id = usage_context.conversation_id or _coerce_uuid(getattr(state, "thread_id", None))

                    # Batch-validate every optional FK once; unknown → NULL, event kept
                    valid_agents = await self._existing_ids(session, AgentModel, {usage_context.agent_id})
                    valid_workflows = await self._existing_ids(session, WorkflowModel, {usage_context.workflow_id})
                    valid_conversations = await self._existing_ids(session, ConversationModel, {conversation_id})
                    provider_ids = {_coerce_uuid(e.get("llm_provider_id")) for e in entries}
                    valid_providers = await self._existing_ids(session, LlmProvidersModel, provider_ids)

                    agent_id = usage_context.agent_id if usage_context.agent_id in valid_agents else None
                    workflow_id = usage_context.workflow_id if usage_context.workflow_id in valid_workflows else None
                    conversation_id = conversation_id if conversation_id in valid_conversations else None

                    event_rows = []
                    for idx, entry in enumerate(entries):
                        provider = entry.get("provider", "") or ""
                        model = entry.get("model", "") or ""
                        input_tokens = int(entry.get("input_tokens", 0) or 0)
                        output_tokens = int(entry.get("output_tokens", 0) or 0)
                        provider_id = _coerce_uuid(entry.get("llm_provider_id"))
                        pricing = _resolve_cost(provider, model, input_tokens, output_tokens)
                        event_rows.append(
                            {
                                "execution_id": str(state.execution_id),
                                "call_index": idx,
                                "source_type": usage_context.source_type,
                                "source": usage_context.source,
                                "purpose": entry.get("purpose"),
                                "agent_id": agent_id,
                                "workflow_id": workflow_id,
                                "llm_provider_id": provider_id if provider_id in valid_providers else None,
                                "llm_analyst_id": None,
                                "conversation_id": conversation_id,
                                "node_id": entry.get("node_id"),
                                "provider_key": _normalize(provider, 64),
                                "model_key": _normalize(model, 512),
                                "input_tokens": input_tokens,
                                "output_tokens": output_tokens,
                                "total_tokens": input_tokens + output_tokens,
                                "token_details": entry.get("token_details"),
                                "occurred_at": occurred_at,
                                **pricing,
                            }
                        )

                    persisted = 0
                    if event_rows:
                        insert_events = insert(LlmUsageEventModel).values(event_rows)
                        insert_events = insert_events.on_conflict_do_nothing(
                            constraint="uq_llm_usage_events_execution_call"
                        )
                        result = await session.execute(insert_events)
                        persisted = result.rowcount or 0

                    receipt = (
                        insert(LlmUsageCaptureRunModel)
                        .values(
                            {
                                "execution_id": str(state.execution_id),
                                "source_type": usage_context.source_type,
                                "source": usage_context.source,
                                "execution_outcome": execution_outcome,
                                "run_status": getattr(state, "status", "idle") or "idle",
                                "expected_entries": len(entries),
                                "persisted_events": persisted,
                                "agent_id": agent_id,
                                "workflow_id": workflow_id,
                                "conversation_id": conversation_id,
                                "occurred_at": occurred_at,
                            }
                        )
                        .on_conflict_do_nothing(constraint="uq_llm_usage_capture_runs_execution")
                    )
                    await session.execute(receipt)

                    await session.commit()
                except Exception:
                    await session.rollback()
                    logger.warning("Failed recording workflow LLM usage", exc_info=True)
                finally:
                    await session.close()
        except Exception:
            logger.warning("Failed opening scope for LLM usage recording", exc_info=True)

    async def record_analyst_call(
        self,
        analysis_execution_id: str,
        call_index: int,
        provider: str,
        model: str,
        input_tokens: int,
        output_tokens: int,
        *,
        source: str = "conversation_analysis",
        conversation_id: Optional[UUID] = None,
        agent_id: Optional[UUID] = None,
        llm_analyst_id: Optional[UUID] = None,
        llm_provider_id: Optional[UUID] = None,
        purpose: Optional[str] = None,
        token_details: Optional[dict[str, Any]] = None,
        run_status: str = "completed",
    ) -> None:
        """
        Retry-safe two-phase analyst capture: a duplicate invocation must never
        overwrite a completed receipt. Completeness is decided by SELECT EXISTS on the
        event, never the insert rowcount
        """
        try:
            async with create_tenant_request_scope():
                session = injector.get(AsyncSession)
                try:
                    if not await self._capture_enabled(session):
                        return

                    occurred_at = utc_now()
                    conversation_id = conversation_id if conversation_id is not None else None
                    valid_conv = await self._existing_ids(session, ConversationModel, {conversation_id})
                    valid_agent = await self._existing_ids(session, AgentModel, {agent_id})
                    valid_analyst = await self._existing_ids(session, LlmAnalystModel, {llm_analyst_id})
                    valid_provider = await self._existing_ids(session, LlmProvidersModel, {llm_provider_id})
                    conversation_id = conversation_id if conversation_id in valid_conv else None
                    agent_id = agent_id if agent_id in valid_agent else None
                    llm_analyst_id = llm_analyst_id if llm_analyst_id in valid_analyst else None
                    llm_provider_id = llm_provider_id if llm_provider_id in valid_provider else None

                    receipt_execution_id = f"{analysis_execution_id}:{call_index}"

                    receipt = (
                        insert(LlmUsageCaptureRunModel)
                        .values(
                            {
                                "execution_id": receipt_execution_id,
                                "source_type": "llm_analyst",
                                "source": source,
                                "execution_outcome": "returned",
                                "run_status": run_status,
                                "expected_entries": 1,
                                "persisted_events": 0,
                                "agent_id": agent_id,
                                "conversation_id": conversation_id,
                                "occurred_at": occurred_at,
                            }
                        )
                        .on_conflict_do_nothing(constraint="uq_llm_usage_capture_runs_execution")
                    )
                    await session.execute(receipt)
                    await session.commit()

                    input_tokens = int(input_tokens or 0)
                    output_tokens = int(output_tokens or 0)
                    pricing = _resolve_cost(provider, model, input_tokens, output_tokens)
                    event = (
                        insert(LlmUsageEventModel)
                        .values(
                            {
                                "execution_id": analysis_execution_id,
                                "call_index": call_index,
                                "source_type": "llm_analyst",
                                "source": source,
                                "purpose": purpose,
                                "agent_id": agent_id,
                                "llm_analyst_id": llm_analyst_id,
                                "llm_provider_id": llm_provider_id,
                                "conversation_id": conversation_id,
                                "provider_key": _normalize(provider, 64),
                                "model_key": _normalize(model, 512),
                                "input_tokens": input_tokens,
                                "output_tokens": output_tokens,
                                "total_tokens": input_tokens + output_tokens,
                                "token_details": token_details,
                                "occurred_at": occurred_at,
                                **pricing,
                            }
                        )
                        .on_conflict_do_nothing(constraint="uq_llm_usage_events_execution_call")
                    )
                    await session.execute(event)
                    await session.commit()

                    event_exists = await session.scalar(
                        select(
                            exists().where(
                                LlmUsageEventModel.execution_id == analysis_execution_id,
                                LlmUsageEventModel.call_index == call_index,
                            )
                        )
                    )
                    if event_exists:
                        await session.execute(
                            LlmUsageCaptureRunModel.__table__.update()
                            .where(LlmUsageCaptureRunModel.execution_id == receipt_execution_id)
                            .values(persisted_events=1)
                        )
                        await session.commit()
                except Exception:
                    await session.rollback()
                    logger.warning("Failed recording analyst LLM usage", exc_info=True)
                finally:
                    await session.close()
        except Exception:
            logger.warning("Failed opening scope for analyst LLM usage recording", exc_info=True)
