"""Unit tests for agent response log persistence"""

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from sqlalchemy.exc import IntegrityError

from app.repositories.agent_response_log import AgentResponseLogRepository


@pytest.fixture(autouse=True)
def _plain_model(monkeypatch):

    class PlainLog:
        def __init__(self, **fields):
            self.__dict__.update(fields)

    monkeypatch.setattr("app.repositories.agent_response_log.AgentResponseLogModel", PlainLog)


class FakeSavepoint:

    def __init__(self, session):
        self.session = session

    async def __aenter__(self):
        self.session.savepoints_opened += 1
        return self

    async def __aexit__(self, exc_type, exc, tb):
        if exc_type is not None:
            self.session.savepoints_rolled_back += 1
        else:
            self.session.savepoints_released += 1
        return False


class FakeSession:
    def __init__(self, flush_error=None):
        self.flush_error = flush_error
        self.added = []
        self.committed = 0
        self.rolled_back = 0
        self.savepoints_opened = 0
        self.savepoints_released = 0
        self.savepoints_rolled_back = 0

    def begin_nested(self):
        return FakeSavepoint(self)

    def add(self, obj):
        self.added.append(obj)

    async def flush(self):
        if self.flush_error is not None:
            raise self.flush_error

    async def commit(self):
        self.committed += 1

    async def rollback(self):
        self.rolled_back += 1

    async def refresh(self, obj):
        return obj


def _integrity_error():
    return IntegrityError("INSERT ...", {}, Exception("duplicate key value"))


async def _log(session, execution_id="exec-1"):
    repo = AgentResponseLogRepository(db=session)
    return await repo.log_response(
        conversation_id=uuid4(),
        transcript_message_id=uuid4(),
        raw_response={"message": "hi"},
        input_tokens=10,
        output_tokens=5,
        total_tokens=15,
        cost_usd=0.001,
        workflow_execution_id=execution_id,
    )


class TestLogResponse:
    @pytest.mark.asyncio
    async def test_writes_inside_a_savepoint_and_commits(self):
        session = FakeSession()
        entry = await _log(session)

        assert session.savepoints_opened == 1
        assert session.savepoints_released == 1
        assert session.committed == 1
        assert entry.workflow_execution_id == "exec-1"
        assert entry.total_tokens == 15

    @pytest.mark.asyncio
    async def test_duplicate_execution_raises_to_the_caller(self):
        session = FakeSession(flush_error=_integrity_error())

        with pytest.raises(IntegrityError):
            await _log(session)

        assert session.savepoints_opened == 1
        assert session.savepoints_rolled_back == 1

    @pytest.mark.asyncio
    async def test_duplicate_never_commits_the_outer_transaction(self):
        session = FakeSession(flush_error=_integrity_error())

        with pytest.raises(IntegrityError):
            await _log(session)

        assert session.committed == 0

    @pytest.mark.asyncio
    async def test_the_violation_surfaces_from_the_flush_not_the_commit(self):
        session = FakeSession(flush_error=_integrity_error())
        session.commit = AsyncMock()

        with pytest.raises(IntegrityError):
            await _log(session)

        session.commit.assert_not_awaited()


class TestSessionStaysUsable:
    @pytest.mark.asyncio
    async def test_reads_still_work_after_a_swallowed_duplicate(self):
        session = FakeSession(flush_error=_integrity_error())
        session.execute = AsyncMock(return_value=MagicMock())

        try:
            await _log(session)
        except IntegrityError:
            pass

        await session.execute("SELECT 1")
        session.execute.assert_awaited_once()
        assert session.rolled_back == 0
