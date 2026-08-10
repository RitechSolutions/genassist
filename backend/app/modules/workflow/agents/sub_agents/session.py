"""Frame-stack access on the root thread's conversation metadata.

One helper, three operations: ``write_frame`` (awaited, size-guarded, re-raises
so a pause is never taken without durable state), ``read_frame_strict``
(fail-closed — only a genuinely absent key routes to the root agent), and
``is_owned`` (never clear another agent's frame). Reuses ``get_metadata`` /
``set_metadata``; no new store.
"""

import json
import logging
from typing import Any

from pydantic import ValidationError

from app.modules.workflow.agents.sub_agents.models import FRAME_VERSION, SubAgentStack

logger = logging.getLogger(__name__)

STACK_KEY = "sub_agent_stack"
MAX_STACK_BYTES = 256 * 1024


class SubAgentSessionError(Exception):
    """Fail-closed signal: the frame exists but can't be trusted/read."""


async def write_frame(memory: Any, stack: SubAgentStack) -> None:
    """Save the handoff stack before the child runs or pauses"""
    payload = stack.model_dump()
    try:
        encoded = json.dumps(payload)
    except (TypeError, ValueError) as exc:
        raise SubAgentSessionError(f"sub-agent handoff state is not JSON-serializable: {exc}") from exc
    if len(encoded) > MAX_STACK_BYTES:
        raise SubAgentSessionError("sub-agent handoff state exceeds size limit")
    await memory.set_metadata(STACK_KEY, payload)


async def clear_stack(memory: Any) -> None:
    await memory.set_metadata(STACK_KEY, None)


async def read_frame_strict(memory: Any) -> SubAgentStack | None:
    """Return the live stack, None (absent/expired/old), or raise fail-closed.

    Only an absent key falls through to the root agent. A read error or a
    same-version corrupt payload raises so clarification text is never routed to
    the wrong agent; an old-version or expired payload is soft-cleared to None.
    """
    try:
        raw = await memory.get_metadata_strict(STACK_KEY)
    except KeyError:
        return None  # genuinely absent -> root path
    except Exception as exc:
        # A Redis/decode error must never look like "absent" (that would route
        # the user's reply to the root agent and strand the child).
        raise SubAgentSessionError(f"sub-agent session read failed: {exc}") from exc

    if raw is None:
        return None
    if not isinstance(raw, dict):
        raise SubAgentSessionError("sub-agent session payload is not an object")

    if raw.get("version") != FRAME_VERSION:
        await clear_stack(memory)
        return None

    try:
        stack = SubAgentStack.model_validate(raw)
    except ValidationError as exc:
        raise SubAgentSessionError(f"sub-agent session payload is corrupt: {exc}") from exc

    top = stack.top()
    if top is None or top.is_expired():
        await clear_stack(memory)
        return None
    return stack


def is_owned(stack: SubAgentStack, agent_id: str, workflow_id: str) -> bool:
    """The stack top belongs to this agent + workflow (else leave it intact)."""
    top = stack.top()
    return bool(top and stack.agent_id == agent_id and top.workflow_id == workflow_id)
