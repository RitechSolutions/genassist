"""Run one child sub-agent turn and shape the delegation envelope"""

import asyncio
import json
import logging
from typing import TYPE_CHECKING, Any, Dict, Literal, Optional

from fastapi_injector import RequestScopeFactory
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.tenant_scope import get_tenant_context, set_tenant_context
from app.dependencies.injector import injector
from app.modules.workflow.agents.sub_agents.models import SubAgentMode
from app.modules.workflow.usage_context import WorkflowUsageContext

if TYPE_CHECKING:
    from app.modules.workflow.engine.workflow_state import WorkflowState

logger = logging.getLogger(__name__)

ENVELOPE_VERSION = 1
_ENVELOPE_KEY = "__sub_agent__"


class Envelope(BaseModel):
    """Delegation result the parent's agent loop consumes"""

    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    version: int = Field(alias=_ENVELOPE_KEY)
    status: Literal["completed", "active"]
    message: str
    child_node_id: str
    mode: SubAgentMode
    invocation_id: str
    task: str


SUB_AGENT_CONTROL_ATTR = "sub_agent_control"


def child_thread_id(root_thread_id: str, child_node_id: str, invocation_id: str) -> str:
    """Invocation-scoped child thread so an unrelated later delegation to the same
    child never inherits this branch's history."""
    return f"{root_thread_id}:sub:{child_node_id}:{invocation_id}"


def discard_child_memory(root_thread_id: str, child_node_id: str, invocation_id: str) -> None:
    """Drop the finished child's cached ConversationMemory"""
    from app.modules.workflow.agents.memory import ConversationMemory

    ConversationMemory.discard(child_thread_id(root_thread_id, child_node_id, invocation_id))


def make_envelope(*, status: str, message: str, child_node_id: str, mode: str, invocation_id: str, task: str) -> str:
    return json.dumps(
        {
            _ENVELOPE_KEY: ENVELOPE_VERSION,
            "status": status,
            "message": message,
            "child_node_id": child_node_id,
            "mode": mode,
            "invocation_id": invocation_id,
            "task": task,
        }
    )


def parse_envelope(text: Any) -> Optional[Dict[str, Any]]:
    """Return a fully validated envelope dict, or None for anything that is not a
    current-version delegation result"""
    if not isinstance(text, str):
        return None
    try:
        data = json.loads(text)
    except (ValueError, TypeError):
        return None
    if not isinstance(data, dict) or data.get(_ENVELOPE_KEY) != ENVELOPE_VERSION:
        return None
    try:
        envelope = Envelope.model_validate(data)
    except ValidationError:
        return None
    return envelope.model_dump(by_alias=True)


def child_completion(child_state: "WorkflowState") -> Optional[Dict[str, Any]]:
    """The finish_task/return_to_parent result, or None if the child didn't complete."""
    return getattr(child_state, SUB_AGENT_CONTROL_ATTR, None)


def child_message(child_state: "WorkflowState") -> str:
    output = child_state.get_last_node_output()
    if isinstance(output, dict):
        return output.get("message", "") or ""
    return "" if output is None else str(output)


def _canonical_session(session: Dict[str, Any]) -> Dict[str, Any]:
    """Strip flatten artifacts and the parent's resume marker so a child inherits a clean namespace"""
    from app.modules.workflow.agents.sub_agents.models import SUB_AGENT_RESUME_KEY

    return {
        key: value
        for key, value in session.items()
        if key != SUB_AGENT_RESUME_KEY
        and not (isinstance(key, str) and (key == "session" or key.startswith("session.")))
    }


def _force_child_pii(nodes: list, child_node_id: str) -> list:
    out = []
    for node in nodes:
        if node.get("id") == child_node_id:
            node = {**node, "data": {**node.get("data", {}), "piiMasking": True}}
        out.append(node)
    return out


def propagate_prompt_cache_diagnostics(child_state: "WorkflowState", parent_state: "WorkflowState") -> None:
    """Carry a child's prompt-caching diagnostics up to the parent, out of band"""
    try:
        merged = getattr(child_state, "prompt_caching_diagnostics", None)
        if not isinstance(merged, dict) or not merged:
            return
        collected = getattr(parent_state, "prompt_caching_diagnostics", None)
        if isinstance(collected, dict):
            collected.update(merged)
    except Exception:
        logger.warning("Failed propagating sub-agent prompt-caching diagnostics", exc_info=True)


async def run_child_turn(
    *,
    workflow: Dict[str, Any],
    root_thread_id: str,
    child_node_id: str,
    invocation_id: str,
    message: str,
    session: Optional[Dict[str, Any]] = None,
    timeout_seconds: float,
    inherit_pii: bool = False,
    usage_sink: Optional[list] = None,
    usage_context: Optional[WorkflowUsageContext] = None,
) -> "WorkflowState":
    """Execute the child once and return its WorkflowState.

    Usage threading is opaque: ``usage_sink`` (initial in-parent delegation) or
    ``usage_context`` (interactive resume) is forwarded to the child engine so
    child LLM calls are captured exactly once.
    """
    from app.modules.workflow.engine.workflow_engine import WorkflowEngine

    nodes = workflow.get("nodes", [])
    if inherit_pii:
        nodes = _force_child_pii(nodes, child_node_id)
    workflow_config = {
        "id": (workflow.get("config") or {}).get("id") or workflow.get("id"),
        "nodes": nodes,
        "edges": workflow.get("edges", []),
    }
    engine = WorkflowEngine(workflow_config)
    thread_id = child_thread_id(root_thread_id, child_node_id, invocation_id)
    # Pass the parent session as one nested object
    input_data = {"message": message}
    canonical = _canonical_session(session or {})
    if canonical:
        input_data["session"] = canonical

    tenant = get_tenant_context()
    from app.core.utils.db_connection_utils import (
        commit_scope_session,
        rollback_scope_session,
    )

    factory = injector.get(RequestScopeFactory)
    async with factory.create_scope():
        set_tenant_context(tenant)
        try:
            child_state = await asyncio.wait_for(
                engine.execute_from_node(
                    start_node_id=child_node_id,
                    input_data=input_data,
                    thread_id=thread_id,
                    persist=False,
                    usage_sink=usage_sink,
                    usage_context=usage_context,
                ),
                timeout=timeout_seconds,
            )
        except Exception:
            # Repos only flush; roll back this child turn's writes on error.
            await rollback_scope_session(context="orchestrator_child_turn")
            raise
        else:
            # Commit this child turn's unit of work (no-op if nothing was written).
            await commit_scope_session(context="orchestrator_child_turn")
        finally:
            try:
                session = injector.get(AsyncSession)
                await session.close()
            except Exception:
                logger.warning("Child-turn DB session close failed", exc_info=True)

    await child_state.get_memory().add_input_output(message, child_message(child_state))
    return child_state
