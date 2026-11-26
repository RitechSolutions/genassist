import logging
from typing import Optional
from uuid import UUID

from injector import inject
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.utils.background_tasks import spawn
from app.core.utils.db_connection_utils import create_tenant_request_scope
from app.db.models.guardrail_event import GuardrailEventModel
from app.dependencies.injector import injector
from app.modules.workflow.guardrails.detectors import check_text
from app.modules.workflow.guardrails.turn import record_usage
from app.modules.workflow.usage_context import WorkflowUsageContext
from app.repositories.guardrail_events import GuardrailEventRepository
from app.schemas.guardrails import GuardrailCheckRequest, GuardrailCheckResponse, GuardrailEventRead

logger = logging.getLogger(__name__)

RECORDED_ACTIONS = {"flagged", "blocked", "error"}


def _clamp(value: Optional[str], limit: int) -> Optional[str]:
    return value[:limit] if isinstance(value, str) else value


@inject
class GuardrailService:
    def __init__(self, repository: GuardrailEventRepository):
        self.repository = repository

    async def try_policy(self, agent_id: UUID, request: GuardrailCheckRequest) -> GuardrailCheckResponse:
        mode = "block" if request.policy.mode == "block" else "detect"
        usage: list[dict] = []
        context = request.previous_reply if request.policy.previous_reply_context else None
        verdicts, blocked = await check_text(request.text, request.policy, "input", mode, usage, context=context)
        record_usage(usage, WorkflowUsageContext(source="guardrail_test", agent_id=agent_id), None)
        return GuardrailCheckResponse(blocked=blocked, verdicts=verdicts)

    async def record_turn_events(
        self,
        agent_id: UUID,
        conversation_id: Optional[UUID],
        input_message_id: Optional[UUID],
        reply_message_id: Optional[UUID],
        registry_response: dict,
    ) -> None:
        execution_id = registry_response.get("execution_id")
        rows = [
            GuardrailEventModel(
                agent_id=agent_id,
                conversation_id=conversation_id,
                transcript_message_id=input_message_id if v.get("stage") == "input" else reply_message_id,
                workflow_execution_id=execution_id,
                stage=v["stage"],
                check_type=_clamp(v["check_type"], 32),
                category=_clamp(v.get("category"), 128),
                detector=v["detector"],
                score=v.get("score"),
                mode=v["mode"],
                action=v["action"],
                source=_clamp(v.get("source"), 128),
            )
            for v in registry_response.get("guardrail_events") or []
            if v.get("action") in RECORDED_ACTIONS
        ]
        if rows:
            await self.repository.add_many(rows)

    async def list_for_conversation(self, conversation_id: UUID) -> list[GuardrailEventRead]:
        rows = await self.repository.list_by_conversation(conversation_id)
        return [GuardrailEventRead.model_validate(row) for row in rows]


def record_events_without_conversation(agent_id: UUID, registry_response: dict) -> None:
    verdicts = registry_response.get("guardrail_events") or []
    if not any(v.get("action") in RECORDED_ACTIONS for v in verdicts):
        return
    try:
        spawn(_record_in_own_scope(agent_id, registry_response), name="guardrail-events")
    except Exception:
        logger.warning("Scheduling guardrail events failed", exc_info=True)


async def _record_in_own_scope(agent_id: UUID, registry_response: dict) -> None:
    async with create_tenant_request_scope():
        session = injector.get(AsyncSession)
        try:
            await injector.get(GuardrailService).record_turn_events(agent_id, None, None, None, registry_response)
            await session.commit()
        finally:
            await session.close()
