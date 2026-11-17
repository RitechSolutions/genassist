import logging
from contextvars import ContextVar
from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any, Optional
from uuid import uuid4

from pydantic import ValidationError

from app.core.utils.background_tasks import spawn
from app.core.utils.date_time_utils import utc_now
from app.modules.workflow.guardrails.detectors import check_text
from app.schemas.guardrails import GuardrailPolicy

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class GuardrailTurn:
    policy: GuardrailPolicy
    blocked_message: str


current_guardrails: ContextVar[Optional[GuardrailTurn]] = ContextVar("guardrail_turn", default=None)


def active_policy(value) -> Optional[GuardrailPolicy]:
    if value is None:
        return None
    try:
        policy = value if isinstance(value, GuardrailPolicy) else GuardrailPolicy.model_validate(value)
    except ValidationError:
        logger.warning("Ignoring an invalid Guardrails policy")
        return None
    return policy if policy.mode != "off" else None


async def start_turn(
    policy: Optional[GuardrailPolicy], agent_id: str, language: Optional[str], live_voice: bool
) -> Optional[GuardrailTurn]:
    if policy is None:
        return None
    if live_voice:
        policy = policy.model_copy(update={"mode": "detect"})
    return GuardrailTurn(policy, await _blocked_message(policy.blocked_message, agent_id, language))


async def _blocked_message(message: str, agent_id: str, language: Optional[str]) -> str:
    if not language:
        return message
    key = f"agent.{agent_id}.guardrails.blocked_message"
    try:
        from app.dependencies.injector import injector
        from app.services.translations import TranslationsService

        resolved = await injector.get(TranslationsService).resolve_many_for_lang({key: message}, language)
        return resolved.get(key) or message
    except Exception as exc:  # translation is best-effort; fall back to the source text
        logger.debug("Blocked message translation lookup failed: %s", exc)
        return message


async def check_input(turn: GuardrailTurn, text: str, form_resume: bool, usage_context, thread_id) -> tuple[list[dict], bool]:
    mode = "detect" if form_resume else turn.policy.mode
    usage: list[dict] = []
    verdicts, blocked = await check_text(text, turn.policy, "input", mode, usage)
    record_usage(usage, usage_context, thread_id)
    return verdicts, blocked


def reply_text(output: Any) -> Optional[str]:
    if output is None:
        return None
    if isinstance(output, dict):
        if output.get("type") == "audio":
            return None
        if output.get("status") == "awaiting_input" and "sub_agent" not in output:
            return None
        return str(output.get("message") or output.get("response") or output)
    return str(output)


def _sub_agent_envelope(output: Any) -> Optional[dict]:
    if isinstance(output, dict) and output.get("status") == "awaiting_input" and isinstance(output.get("sub_agent"), dict):
        return output["sub_agent"]
    return None


async def guard_state_reply(state) -> None:
    turn = current_guardrails.get()
    if turn is None or not turn.policy.check_replies:
        return
    try:
        envelope = _sub_agent_envelope(state.output)
        text = envelope.get("message") if envelope is not None else reply_text(state.output)
        if not text:
            return
        usage: list[dict] = []
        verdicts, blocked = await check_text(str(text), turn.policy, "output", turn.policy.mode, usage)
        for entry in usage:
            state.add_llm_usage(**entry)
        state.guardrail_events.extend(verdicts)
        if not blocked:
            return
        if envelope is not None:
            envelope["message"] = turn.blocked_message
        elif isinstance(state.output, str):
            state.output = turn.blocked_message
        else:
            state.output = {"message": turn.blocked_message}
    except Exception:
        logger.warning("Guardrail reply check failed; the reply is kept", exc_info=True)


async def guard_routed_reply(reply: str, usage_context, thread_id) -> tuple[str, list[dict]]:
    turn = current_guardrails.get()
    if turn is None or not turn.policy.check_replies or not reply:
        return reply, []
    usage: list[dict] = []
    verdicts, blocked = await check_text(reply, turn.policy, "output", turn.policy.mode, usage)
    record_usage(usage, usage_context, thread_id)
    return (turn.blocked_message if blocked else reply), verdicts


def record_usage(usage: list[dict], usage_context, thread_id) -> None:
    if not usage or usage_context is None:
        return
    snapshot = SimpleNamespace(
        execution_id=f"guardrail:{uuid4()}", llm_usage=list(usage), thread_id=thread_id, status="completed"
    )
    try:
        from app.services.llm_usage_recorder import LlmUsageRecorder

        spawn(
            LlmUsageRecorder().record_workflow_state(snapshot, usage_context, "returned", occurred_at=utc_now()),
            name="guardrail-usage",
        )
    except Exception:
        logger.warning("Scheduling guardrail usage capture failed", exc_info=True)
