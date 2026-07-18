"""Run one child sub-agent turn and shape the delegation envelope.

The child runs in its own WorkflowEngine on an invocation-scoped thread (branch
isolation), ``persist=False`` inside a fresh request scope so a timeout
cancellation can't corrupt the parent's session; its turn is then awaited-durable
before any frame is written. The envelope is the only thing the parent's agent
loop sees — never the child's state.
"""

import asyncio
import json
import logging
from typing import Any, Dict, Optional

from fastapi_injector import RequestScopeFactory
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.tenant_scope import get_tenant_context, set_tenant_context
from app.dependencies.injector import injector

logger = logging.getLogger(__name__)

ENVELOPE_VERSION = 1
_ENVELOPE_KEY = "__sub_agent__"

# Completion marker the child's finish_task/return_to_parent sets on its OWN
# state; read here to classify. Never an output key (would leak to the response).
SUB_AGENT_CONTROL_ATTR = "sub_agent_control"


def child_thread_id(root_thread_id: str, child_node_id: str, invocation_id: str) -> str:
    """Invocation-scoped child thread so an unrelated later delegation to the same
    child never inherits this branch's history."""
    return f"{root_thread_id}:sub:{child_node_id}:{invocation_id}"


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
    """Return the envelope dict only when name- and version-gated; else None."""
    if not isinstance(text, str):
        return None
    try:
        data = json.loads(text)
    except (ValueError, TypeError):
        return None
    if not isinstance(data, dict) or data.get(_ENVELOPE_KEY) != ENVELOPE_VERSION:
        return None
    if data.get("status") not in ("completed", "active"):
        return None
    return data


def child_completion(child_state: Any) -> Optional[Dict[str, Any]]:
    """The finish_task/return_to_parent result, or None if the child didn't complete."""
    return getattr(child_state, SUB_AGENT_CONTROL_ATTR, None)


def child_message(child_state: Any) -> str:
    output = child_state.get_last_node_output()
    if isinstance(output, dict):
        return output.get("message", "") or ""
    return "" if output is None else str(output)


def _force_child_pii(nodes: list, child_node_id: str) -> list:
    """Copy of nodes with the child's piiMasking forced on (parent masked, so the
    child must mask for its own LLM); the shared workflow is never mutated."""
    out = []
    for node in nodes:
        if node.get("id") == child_node_id:
            node = {**node, "data": {**node.get("data", {}), "piiMasking": True}}
        out.append(node)
    return out


async def run_child_turn(
    *,
    workflow: Dict[str, Any],
    root_thread_id: str,
    child_node_id: str,
    invocation_id: str,
    message: str,
    session_flat: Optional[Dict[str, Any]] = None,
    timeout_seconds: float,
    inherit_pii: bool = False,
) -> Any:
    """Execute the child once and return its WorkflowState (never catches BaseException)."""
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
    input_data = {"message": message, **(session_flat or {})}

    tenant = get_tenant_context()
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
                ),
                timeout=timeout_seconds,
            )
        finally:
            try:
                session = injector.get(AsyncSession)
                await session.close()
            except Exception:  # pylint: disable=broad-except
                pass

    # persist=False + engine's fire-and-forget write, so make the turn durable here
    # BEFORE the caller writes an "active" frame that points at this thread.
    await child_state.get_memory().add_input_output(message, child_message(child_state))
    return child_state
