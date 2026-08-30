import asyncio
import logging
from datetime import datetime
from decimal import Decimal
from typing import Any, Optional
from uuid import UUID
from weakref import WeakKeyDictionary

from sqlalchemy import exists, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config.llm_pricing import (
    PricingStatus,
    blended_token_cost,
    canonical_prompt_tokens,
    inclusive_cache_fallback,
    resolve_pricing,
)
from app.core.utils.date_time_utils import utc_now
from app.core.utils.db_connection_utils import create_tenant_request_scope
from app.core.utils.llm_usage_utils import extract_cache_tokens, is_usage_metadata_missing, usage_or_placeholder
from app.core.utils.uuid_utils import coerce_uuid
from app.db.events.group_scope import GROUP_SCOPE_BYPASS_FLAG
from app.db.models.agent import AgentModel
from app.db.models.conversation import ConversationModel
from app.db.models.llm import LlmAnalystModel, LlmProvidersModel
from app.db.models.llm_usage import (
    CONTROL_SINGLETON_KEY,
    RUN_STATUSES,
    LlmUsageCaptureRunModel,
    LlmUsageControlModel,
    LlmUsageEventModel,
)
from app.db.models.workflow import WorkflowModel
from app.dependencies.injector import injector
from app.modules.workflow.usage_context import WorkflowUsageContext

logger = logging.getLogger(__name__)

_UNPRICED = {
    "input_per_1k": None,
    "output_per_1k": None,
    "cache_read_per_1k": None,
    "cache_creation_per_1k": None,
    "cost_usd": None,
    "pricing_status": PricingStatus.UNPRICED.value,
}

# Deferred captures outlive their request, so cap how many share the tenant pool at once
_CAPTURE_CONCURRENCY = 4
_capture_slots: WeakKeyDictionary = WeakKeyDictionary()


def _capture_slot() -> asyncio.Semaphore:
    """Bound per running loop. Celery runs each task on a fresh one, and a single
    module-level semaphore would stay bound to a closed loop"""
    loop = asyncio.get_running_loop()
    slot = _capture_slots.get(loop)
    if slot is None:
        slot = asyncio.Semaphore(_CAPTURE_CONCURRENCY)
        _capture_slots[loop] = slot
    return slot


def _normalize(value: Optional[str], limit: int) -> Optional[str]:
    """Lowercased lookup keys (provider, model)"""
    if not value:
        return None
    return str(value).lower().strip()[:limit] or None


def _clamp(value: Optional[str], limit: int) -> Optional[str]:
    """Truncate a free-form label to its column width, preserving case"""
    if not value:
        return None
    return str(value)[:limit] or None


def _clamp_run_status(value: Any) -> str:
    status = str(value or "").strip().lower()
    return status if status in RUN_STATUSES else "completed"


def _total_tokens(entry: dict[str, Any], input_tokens: int, output_tokens: int) -> int:
    """Use the larger of the provider's total and input+output.

    Providers sometimes report a total bigger than the parts (e.g. reasoning or
    cached prompt). The ledger CHECK needs that larger value.
    """
    raw = entry.get("total_tokens")
    reported = int(raw) if isinstance(raw, (int, float)) and not isinstance(raw, bool) else 0
    return max(reported, input_tokens + output_tokens)


def _token_columns(
    provider: str, entry: dict[str, Any], input_tokens: int, output_tokens: int, token_details: Any
) -> dict[str, Any]:
    """Store the provider's token counts as reported, plus the canonical prompt total"""
    cache_read, cache_creation = extract_cache_tokens(token_details)
    provider_key = (provider or "").strip().lower()
    return {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": _total_tokens(entry, input_tokens, output_tokens),
        "token_details": token_details,
        "cache_read_tokens": cache_read,
        "cache_creation_tokens": cache_creation,
        "prompt_tokens": canonical_prompt_tokens(provider_key, input_tokens, cache_read, cache_creation),
    }


def _resolve_cost(
    provider: str,
    model: str,
    input_tokens: int,
    output_tokens: int,
    configured_rates: Optional[dict[str, Any]] = None,
    usage_missing: bool = False,
    cache_read_tokens: int = 0,
    cache_creation_tokens: int = 0,
) -> dict[str, Any]:
    """Snapshot the rates + cost for one call. No rate, or no reported usage → NULL cost"""
    if usage_missing:
        return dict(_UNPRICED)
    resolution = resolve_pricing(provider, model, configured_rates)
    if resolution.status is PricingStatus.UNPRICED:
        return dict(_UNPRICED)

    provider_key = (provider or "").strip().lower()
    read_rate = inclusive_cache_fallback(provider_key, resolution.cache_read_per_1k, resolution.input_per_1k)
    creation_rate = inclusive_cache_fallback(provider_key, resolution.cache_creation_per_1k, resolution.input_per_1k)
    cost = blended_token_cost(
        provider_key,
        input_tokens,
        output_tokens,
        cache_read_tokens,
        cache_creation_tokens,
        resolution.input_per_1k,
        resolution.output_per_1k,
        read_rate,
        creation_rate,
        Decimal(1000),
    )
    cached = max(int(cache_read_tokens), 0) > 0 or max(int(cache_creation_tokens), 0) > 0
    return {
        "input_per_1k": resolution.input_per_1k,
        "output_per_1k": resolution.output_per_1k,
        "cache_read_per_1k": read_rate if cached else None,
        "cache_creation_per_1k": creation_rate if cached else None,
        "cost_usd": cost,
        "pricing_status": resolution.status.value if cost is not None else PricingStatus.UNPRICED.value,
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

    async def _configured_rates(self, session: AsyncSession) -> dict[str, dict[str, dict[str, Any]]]:
        """Load this tenant's rate rows once for the batch,
        via the recorder's own request scope"""
        try:
            from app.repositories.llm_cost_rates import LlmCostRateRepository

            rows = await injector.get(LlmCostRateRepository).list_active()
        except Exception:
            await session.rollback()
            logger.warning("Loading LLM cost rates failed; pricing from bundled rates only", exc_info=True)
            return {}

        nested: dict[str, dict[str, dict[str, Any]]] = {}
        for row in rows:
            provider_key = _normalize(row.provider_key, 64)
            model_key = _normalize(row.model_key, 512)
            if not provider_key or not model_key:
                continue
            nested.setdefault(provider_key, {})[model_key] = {
                "input_per_1k": row.input_per_1k,
                "output_per_1k": row.output_per_1k,
                "cache_read_per_1k": getattr(row, "cache_read_per_1k", None),
                "cache_creation_per_1k": getattr(row, "cache_creation_per_1k", None),
            }
        return nested

    async def _persisted_event_count(self, session: AsyncSession, execution_id: str) -> int:
        result = await session.execute(
            select(func.count())
            .select_from(LlmUsageEventModel)
            .where(
                LlmUsageEventModel.execution_id == execution_id,
                LlmUsageEventModel.is_deleted == 0,
            )
        )
        return int(result.scalar() or 0)

    async def _existing_ids(self, session: AsyncSession, model, ids: set[UUID]) -> set[UUID]:
        """One SELECT per FK type; ids not present come back absent so callers NULL them"""
        ids = {i for i in ids if i is not None}
        if not ids:
            return set()
        stmt = select(model.id).where(model.id.in_(ids)).execution_options(**{GROUP_SCOPE_BYPASS_FLAG: True})
        result = await session.execute(stmt)
        return {row[0] for row in result.all()}

    async def _agent_for_workflow(self, session: AsyncSession, workflow_id: Optional[UUID]) -> Optional[UUID]:
        """Return the live agent that owns ``workflow_id``, or None if it's not provable"""
        if workflow_id is None:
            return None
        stmt = (
            select(AgentModel.id)
            .where(AgentModel.workflow_id == workflow_id, AgentModel.is_deleted == 0)
            .limit(2)
            .execution_options(**{GROUP_SCOPE_BYPASS_FLAG: True})
        )
        rows = (await session.execute(stmt)).all()
        return rows[0][0] if len(rows) == 1 else None

    async def record_workflow_state(
        self,
        state,
        usage_context: WorkflowUsageContext,
        execution_outcome: str,
        occurred_at: Optional[datetime] = None,
    ) -> None:
        """Deferred callers pass the scheduling-time ``occurred_at`` so a backlog
        cannot shift a run's spend into the next reporting day"""
        try:
            async with _capture_slot():
                async with create_tenant_request_scope():
                    session = injector.get(AsyncSession)
                    try:
                        if not await self._capture_enabled(session):
                            return

                        entries = list(getattr(state, "llm_usage", []) or [])
                        configured_rates = await self._configured_rates(session) if entries else {}
                        occurred_at = occurred_at or utc_now()
                        conversation_id = usage_context.conversation_id or coerce_uuid(getattr(state, "thread_id", None))

                        valid_agents = await self._existing_ids(session, AgentModel, {usage_context.agent_id})
                        valid_workflows = await self._existing_ids(session, WorkflowModel, {usage_context.workflow_id})
                        valid_conversations = await self._existing_ids(session, ConversationModel, {conversation_id})
                        provider_ids = {coerce_uuid(e.get("llm_provider_id")) for e in entries}
                        valid_providers = await self._existing_ids(session, LlmProvidersModel, provider_ids)

                        agent_id = usage_context.agent_id if usage_context.agent_id in valid_agents else None
                        workflow_id = usage_context.workflow_id if usage_context.workflow_id in valid_workflows else None
                        conversation_id = conversation_id if conversation_id in valid_conversations else None
                        if agent_id is None:
                            agent_id = await self._agent_for_workflow(session, workflow_id)

                        event_rows = []
                        for idx, entry in enumerate(entries):
                            provider = entry.get("provider", "") or ""
                            model = entry.get("model", "") or ""
                            input_tokens = int(entry.get("input_tokens", 0) or 0)
                            output_tokens = int(entry.get("output_tokens", 0) or 0)
                            provider_id = coerce_uuid(entry.get("llm_provider_id"))
                            token_details = entry.get("token_details")
                            token_columns = _token_columns(provider, entry, input_tokens, output_tokens, token_details)
                            pricing = _resolve_cost(
                                provider,
                                model,
                                input_tokens,
                                output_tokens,
                                configured_rates,
                                usage_missing=is_usage_metadata_missing(token_details),
                                cache_read_tokens=token_columns["cache_read_tokens"],
                                cache_creation_tokens=token_columns["cache_creation_tokens"],
                            )
                            event_rows.append(
                                {
                                    "execution_id": str(state.execution_id),
                                    "call_index": idx,
                                    "source_type": _clamp(usage_context.source_type, 32),
                                    "source": _clamp(usage_context.source, 64),
                                    "purpose": _clamp(entry.get("purpose"), 64),
                                    "agent_id": agent_id,
                                    "workflow_id": workflow_id,
                                    "llm_provider_id": provider_id if provider_id in valid_providers else None,
                                    "llm_analyst_id": None,
                                    "conversation_id": conversation_id,
                                    "node_id": _clamp(entry.get("node_id"), 128),
                                    "provider_key": _normalize(provider, 64),
                                    "model_key": _normalize(model, 512),
                                    **token_columns,
                                    "occurred_at": occurred_at,
                                    **pricing,
                                }
                            )

                        if event_rows:
                            insert_events = insert(LlmUsageEventModel).values(event_rows)
                            insert_events = insert_events.on_conflict_do_nothing(
                                constraint="uq_llm_usage_events_execution_call"
                            )
                            await session.execute(insert_events)
                        persisted = await self._persisted_event_count(session, str(state.execution_id))

                        receipt = (
                            insert(LlmUsageCaptureRunModel)
                            .values(
                                {
                                    "execution_id": str(state.execution_id),
                                    "source_type": _clamp(usage_context.source_type, 32),
                                    "source": _clamp(usage_context.source, 64),
                                    "execution_outcome": execution_outcome,
                                    "run_status": _clamp_run_status(getattr(state, "status", None)),
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

    async def record_evaluation_calls(
        self,
        execution_id: str,
        entries: list[dict[str, Any]],
        *,
        workflow_id: Optional[UUID] = None,
        agent_id: Optional[UUID] = None,
        source: str = "test_suite",
        occurred_at: Optional[datetime] = None,
    ) -> None:
        """One batch per evaluated case: the case's judge events plus a single receipt"""
        if not entries:
            return
        try:
            async with _capture_slot():
                async with create_tenant_request_scope():
                    session = injector.get(AsyncSession)
                    try:
                        if not await self._capture_enabled(session):
                            return

                        configured_rates = await self._configured_rates(session)
                        occurred_at = occurred_at or utc_now()

                        valid_workflows = await self._existing_ids(session, WorkflowModel, {workflow_id})
                        valid_agents = await self._existing_ids(session, AgentModel, {agent_id})
                        provider_ids = {coerce_uuid(e.get("llm_provider_id")) for e in entries}
                        valid_providers = await self._existing_ids(session, LlmProvidersModel, provider_ids)

                        workflow_id = workflow_id if workflow_id in valid_workflows else None
                        if agent_id not in valid_agents:
                            agent_id = await self._agent_for_workflow(session, workflow_id)

                        event_rows = []
                        for entry in entries:
                            usage = usage_or_placeholder(entry.get("usage"))
                            input_tokens = int(usage.get("input_tokens") or 0)
                            output_tokens = int(usage.get("output_tokens") or 0)
                            token_details = usage.get("token_details")
                            provider = entry.get("provider", "") or ""
                            model = entry.get("model", "") or ""
                            provider_id = coerce_uuid(entry.get("llm_provider_id"))
                            token_columns = _token_columns(provider, usage, input_tokens, output_tokens, token_details)
                            pricing = _resolve_cost(
                                provider,
                                model,
                                input_tokens,
                                output_tokens,
                                configured_rates,
                                usage_missing=is_usage_metadata_missing(token_details),
                                cache_read_tokens=token_columns["cache_read_tokens"],
                                cache_creation_tokens=token_columns["cache_creation_tokens"],
                            )
                            event_rows.append(
                                {
                                    "execution_id": execution_id,
                                    "call_index": int(entry.get("call_index") or 0),
                                    "source_type": "evaluation",
                                    "source": _clamp(source, 64),
                                    "purpose": _clamp(entry.get("purpose"), 64),
                                    "agent_id": agent_id,
                                    "workflow_id": workflow_id,
                                    "llm_provider_id": provider_id if provider_id in valid_providers else None,
                                    "llm_analyst_id": None,
                                    "conversation_id": None,
                                    "node_id": None,
                                    "provider_key": _normalize(provider, 64),
                                    "model_key": _normalize(model, 512),
                                    **token_columns,
                                    "occurred_at": occurred_at,
                                    **pricing,
                                }
                            )

                        insert_events = (
                            insert(LlmUsageEventModel)
                            .values(event_rows)
                            .on_conflict_do_nothing(constraint="uq_llm_usage_events_execution_call")
                        )
                        await session.execute(insert_events)
                        persisted = await self._persisted_event_count(session, execution_id)

                        receipt = (
                            insert(LlmUsageCaptureRunModel)
                            .values(
                                {
                                    "execution_id": execution_id,
                                    "source_type": "evaluation",
                                    "source": _clamp(source, 64),
                                    "execution_outcome": "returned",
                                    "run_status": "completed",
                                    "expected_entries": len(entries),
                                    "persisted_events": persisted,
                                    "agent_id": agent_id,
                                    "workflow_id": workflow_id,
                                    "occurred_at": occurred_at,
                                }
                            )
                            .on_conflict_do_nothing(constraint="uq_llm_usage_capture_runs_execution")
                        )
                        await session.execute(receipt)

                        await session.commit()
                    except Exception:
                        await session.rollback()
                        logger.warning("Failed recording evaluation LLM usage", exc_info=True)
                    finally:
                        await session.close()
        except Exception:
            logger.warning("Failed opening scope for evaluation LLM usage recording", exc_info=True)

    async def record_analyst_call(
        self,
        analysis_execution_id: str,
        call_index: int,
        provider: str,
        model: str,
        usage: Optional[dict[str, Any]] = None,
        *,
        source: str = "conversation_analysis",
        conversation_id: Optional[UUID] = None,
        agent_id: Optional[UUID] = None,
        llm_analyst_id: Optional[UUID] = None,
        llm_provider_id: Optional[UUID] = None,
        purpose: Optional[str] = None,
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
                                "source": _clamp(source, 64),
                                "execution_outcome": "returned",
                                "run_status": _clamp_run_status(run_status),
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

                    entry = usage_or_placeholder(usage)
                    input_tokens = int(entry.get("input_tokens") or 0)
                    output_tokens = int(entry.get("output_tokens") or 0)
                    token_details = entry.get("token_details")
                    configured_rates = await self._configured_rates(session)
                    token_columns = _token_columns(provider, entry, input_tokens, output_tokens, token_details)
                    pricing = _resolve_cost(
                        provider,
                        model,
                        input_tokens,
                        output_tokens,
                        configured_rates,
                        usage_missing=is_usage_metadata_missing(token_details),
                        cache_read_tokens=token_columns["cache_read_tokens"],
                        cache_creation_tokens=token_columns["cache_creation_tokens"],
                    )
                    event = (
                        insert(LlmUsageEventModel)
                        .values(
                            {
                                "execution_id": analysis_execution_id,
                                "call_index": call_index,
                                "source_type": "llm_analyst",
                                "source": _clamp(source, 64),
                                "purpose": _clamp(purpose, 64),
                                "agent_id": agent_id,
                                "llm_analyst_id": llm_analyst_id,
                                "llm_provider_id": llm_provider_id,
                                "conversation_id": conversation_id,
                                "provider_key": _normalize(provider, 64),
                                "model_key": _normalize(model, 512),
                                **token_columns,
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
