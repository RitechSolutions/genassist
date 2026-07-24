"""Frame session round-trip, fail-closed read, ownership, oversize, expiry"""

import json
from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from app.modules.workflow.agents.sub_agents.models import ParentResume, SubAgentFrame, SubAgentStack
from app.modules.workflow.agents.sub_agents.session import (
    STACK_KEY,
    SubAgentSessionError,
    is_owned,
    read_frame_strict,
    write_frame,
)


class FakeMemory:

    def __init__(self):
        self.metadata = {}

    async def set_metadata(self, key, value):
        self.metadata[key] = json.loads(json.dumps(value, default=str)) if value is not None else None

    async def get_metadata(self, key, default=None):
        return self.metadata.get(key, default)

    async def get_metadata_strict(self, key):
        if key not in self.metadata:
            raise KeyError(key)
        return self.metadata[key]


class RaisingMemory(FakeMemory):
    async def get_metadata_strict(self, key):
        raise RuntimeError("redis down")


class SwallowingMemory(FakeMemory):

    async def get_metadata(self, key, default=None):
        return default

    async def get_metadata_strict(self, key):
        raise RuntimeError("redis down")


def _frame(**overrides):
    base = dict(
        child_node_id="c",
        parent_node_id="p",
        workflow_id="wf1",
        invocation_id="inv1",
        mode="task",
        task="do it",
    )
    base.update(overrides)
    return SubAgentFrame(**base)


def _stack(agent_id="agentA", frames=None):
    return SubAgentStack(agent_id=agent_id, frames=frames if frames is not None else [_frame()])


@pytest.mark.asyncio
async def test_round_trip():
    mem = FakeMemory()
    stack = _stack()
    await write_frame(mem, stack)
    loaded = await read_frame_strict(mem)
    assert loaded is not None
    assert loaded.agent_id == "agentA"
    assert loaded.top().child_node_id == "c"


@pytest.mark.asyncio
async def test_absent_key_returns_none():
    assert await read_frame_strict(FakeMemory()) is None


@pytest.mark.asyncio
async def test_expired_frame_cleared_to_none():
    mem = FakeMemory()
    past = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    await write_frame(mem, _stack(frames=[_frame(expires_at=past)]))
    assert await read_frame_strict(mem) is None
    assert mem.metadata[STACK_KEY] is None


@pytest.mark.asyncio
async def test_unknown_version_cleared_to_none():
    mem = FakeMemory()
    mem.metadata[STACK_KEY] = {"version": 999, "agent_id": "agentA", "frames": []}
    assert await read_frame_strict(mem) is None
    assert mem.metadata[STACK_KEY] is None


@pytest.mark.asyncio
async def test_corrupt_same_version_fails_closed_and_keeps_frame():
    mem = FakeMemory()
    mem.metadata[STACK_KEY] = {"version": 1, "unexpected": True}
    with pytest.raises(SubAgentSessionError):
        await read_frame_strict(mem)
    assert mem.metadata[STACK_KEY] == {"version": 1, "unexpected": True}


@pytest.mark.asyncio
async def test_non_object_payload_fails_closed():
    mem = FakeMemory()
    mem.metadata[STACK_KEY] = "not a dict"
    with pytest.raises(SubAgentSessionError):
        await read_frame_strict(mem)


@pytest.mark.asyncio
async def test_read_error_fails_closed():
    with pytest.raises(SubAgentSessionError):
        await read_frame_strict(RaisingMemory())


@pytest.mark.asyncio
async def test_swallowing_backend_still_fails_closed():
    with pytest.raises(SubAgentSessionError):
        await read_frame_strict(SwallowingMemory())


def test_extra_keys_forbidden():
    with pytest.raises(ValidationError):
        SubAgentStack(agent_id="a", frames=[], surprise=1)


@pytest.mark.asyncio
async def test_oversize_fails_handoff_without_dropping_node_outputs():
    mem = FakeMemory()
    big_outputs = {"node": {"blob": "x" * 300_000}}
    frame = _frame(parent_resume=ParentResume(node_outputs=big_outputs))
    stack = _stack(frames=[frame])
    with pytest.raises(SubAgentSessionError):
        await write_frame(mem, stack)
    assert stack.top().parent_resume.node_outputs == big_outputs
    assert STACK_KEY not in mem.metadata


@pytest.mark.asyncio
async def test_non_serializable_frame_fails_before_write():
    mem = FakeMemory()
    frame = _frame(parent_resume=ParentResume(node_outputs={"agent": {"input": object()}}))
    with pytest.raises(SubAgentSessionError):
        await write_frame(mem, _stack(frames=[frame]))
    assert STACK_KEY not in mem.metadata


def test_ownership_checks():
    stack = _stack(agent_id="agentA", frames=[_frame(workflow_id="wf1")])
    assert is_owned(stack, "agentA", "wf1")
    assert not is_owned(stack, "agentB", "wf1")
    assert not is_owned(stack, "agentA", "wf2")


@pytest.mark.asyncio
async def test_unowned_frame_left_intact_on_read():
    mem = FakeMemory()
    await write_frame(mem, _stack(agent_id="agentA"))
    loaded = await read_frame_strict(mem)
    assert loaded is not None
    assert not is_owned(loaded, "agentB", "wf1")
    assert mem.metadata[STACK_KEY] is not None
