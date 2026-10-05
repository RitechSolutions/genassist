"""Unit tests pinning that the custom-attributes backfill never bumps conversations.updated_at"""

import asyncio
import json
from uuid import uuid4

import pytest
from sqlalchemy.sql import Update

import app.dependencies.injector as injector_module
from app.tasks.backfill_custom_attributes import backfill_custom_attributes_async

WORKFLOW_NODES = [
    {
        "id": "chat-input",
        "type": "chatInputNode",
        "data": {"inputSchema": {"customer_tier": {"useInFilter": True}}},
    }
]


def _raw(output: dict) -> str:
    return json.dumps(
        {
            "row_agent_response": {
                "state": {"nodeExecutionStatus": {"chat-input": {"type": "chatInputNode", "output": output}}}
            }
        }
    )


class _Result:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return self._rows


class FakeSession:
    def __init__(self, conversation_rows, log_rows):
        self.batches = [(conversation_rows, log_rows), ([], [])]
        self.updates = []
        self._pending_logs = None

    async def execute(self, statement):
        if isinstance(statement, Update):
            self.updates.append(statement)
            return None
        if self._pending_logs is None:
            conversation_rows, log_rows = self.batches.pop(0)
            if conversation_rows:
                self._pending_logs = log_rows
            return _Result(conversation_rows)
        rows, self._pending_logs = self._pending_logs, None
        return _Result(rows)

    async def commit(self):
        return None


def _run(monkeypatch, session, *, force):
    monkeypatch.setattr(injector_module.injector, "get", lambda _: session)
    return asyncio.run(backfill_custom_attributes_async(force=force))


@pytest.fixture
def conversations():
    with_attrs, without_attrs, logless = uuid4(), uuid4(), uuid4()
    rows = [(with_attrs, WORKFLOW_NODES), (without_attrs, WORKFLOW_NODES), (logless, WORKFLOW_NODES)]
    logs = [
        (with_attrs, _raw({"customer_tier": "gold"})),
        (without_attrs, _raw({"not_filterable": "x"})),
    ]
    return rows, logs, (with_attrs, without_attrs, logless)


def test_force_backfill_carries_updated_at_on_every_write(monkeypatch, conversations):
    rows, logs, _ = conversations
    session = FakeSession(rows, logs)
    result = _run(monkeypatch, session, force=True)

    assert result == {"status": "completed", "updated": 1}
    assert len(session.updates) == 3, "force must write the attribute row plus both cleared rows"
    for statement in session.updates:
        assert "updated_at=conversations.updated_at" in str(statement)


def test_incremental_backfill_only_writes_extracted_attributes(monkeypatch, conversations):
    rows, logs, _ = conversations
    session = FakeSession(rows, logs)
    result = _run(monkeypatch, session, force=False)

    assert result == {"status": "completed", "updated": 1}
    assert len(session.updates) == 1, "without force, conversations with no attributes stay untouched"
    assert "updated_at=conversations.updated_at" in str(session.updates[0])
