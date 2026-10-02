"""Unit tests for the per-conversation scopes and attempt cap of the analysis backfill"""

import logging
from contextlib import asynccontextmanager
from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

import app.core.utils.db_connection_utils as db_connection_utils
import app.tasks.conversations_tasks as tasks_module
from app.repositories.conversations import ConversationRepository


class FakeRepo:
    def __init__(self, calls, candidates):
        self.calls = calls
        self.candidates = candidates

    async def get_finalized_without_analysis(self, limit=100, *, max_attempts, max_age_days, retry_delay_minutes):
        self.calls.append(("select", max_attempts, max_age_days, retry_delay_minutes))
        return self.candidates

    async def mark_analysis_attempt(self, conversation_id, error=None):
        self.calls.append(("mark", conversation_id))

    async def set_analysis_last_error(self, conversation_id, error):
        self.calls.append(("last_error", conversation_id, error))


class FakeSession:
    def __init__(self, calls):
        self.calls = calls

    async def commit(self):
        self.calls.append("commit")

    async def close(self):
        self.calls.append("close")


class FakeService:
    def __init__(self, calls, failing):
        self.calls = calls
        self.failing = failing

    async def re_analyze_conversation(self, conversation_id):
        self.calls.append(("analyze", conversation_id))
        if conversation_id in self.failing:
            raise RuntimeError("provider down")


@pytest.fixture
def backfill(monkeypatch):
    calls = []

    @asynccontextmanager
    async def _scope():
        calls.append("enter")
        try:
            yield
        finally:
            calls.append("exit")

    async def _release(context=None, session=None):
        calls.append("release")
        return True

    def _run(candidates, failing=()):
        repo = FakeRepo(calls, candidates)
        service = FakeService(calls, set(failing))
        session = FakeSession(calls)

        def _get(cls):
            if cls is AsyncSession:
                return session
            calls.append(("get", cls.__name__))
            return repo if cls is ConversationRepository else service

        monkeypatch.setattr(tasks_module.injector, "get", _get)
        return tasks_module.backfill_missing_conversation_analyses_async()

    monkeypatch.setattr(db_connection_utils, "create_tenant_request_scope", _scope)
    monkeypatch.setattr(db_connection_utils, "release_idle_connection", _release)
    monkeypatch.setattr(tasks_module.settings, "CONVERSATION_ANALYSIS_BACKFILL_MAX_ATTEMPTS", 3)
    monkeypatch.setattr(tasks_module.settings, "CONVERSATION_ANALYSIS_BACKFILL_MAX_AGE_DAYS", 30)
    monkeypatch.setattr(tasks_module.settings, "CONVERSATION_ANALYSIS_BACKFILL_RETRY_DELAY_MINUTES", 60)
    return SimpleNamespace(run=_run, calls=calls)


def _candidate(attempts=0):
    return SimpleNamespace(id=uuid4(), analysis_attempts=attempts)


def _scope(*calls, committed=True):
    return ["enter", *calls, *(["commit"] if committed else []), "close", "exit"]


@pytest.mark.asyncio
async def test_each_conversation_runs_in_its_own_scopes_and_a_failure_does_not_stop_the_next(backfill):
    failed, ok = _candidate(), _candidate()

    result = await backfill.run([failed, ok], failing={failed.id})

    repo, service = ("get", "ConversationRepository"), ("get", "ConversationService")
    assert backfill.calls == [
        repo,
        ("select", 3, 30, 60),
        "release",
        *_scope(repo, ("mark", failed.id)),
        *_scope(service, ("analyze", failed.id), committed=False),
        *_scope(repo, ("last_error", failed.id, "RuntimeError: provider down")),
        *_scope(repo, ("mark", ok.id)),
        *_scope(service, ("analyze", ok.id), repo, ("last_error", ok.id, None)),
    ]
    assert result == {"backfilled": 1, "failed": 1, "capped": 0}


@pytest.mark.asyncio
async def test_a_failure_on_the_last_allowed_attempt_is_capped(backfill, caplog):
    last = _candidate(attempts=2)

    with caplog.at_level(logging.WARNING, logger=tasks_module.__name__):
        result = await backfill.run([last], failing={last.id})

    assert result == {"backfilled": 0, "failed": 1, "capped": 1}
    warning = next(r for r in caplog.records if r.levelno == logging.WARNING)
    assert str(last.id)[:8] in warning.getMessage()
    assert str(last.id) not in warning.getMessage()


@pytest.mark.asyncio
async def test_settings_reach_the_query_and_no_candidates_is_a_no_op(backfill, monkeypatch):
    monkeypatch.setattr(tasks_module.settings, "CONVERSATION_ANALYSIS_BACKFILL_MAX_ATTEMPTS", 5)
    monkeypatch.setattr(tasks_module.settings, "CONVERSATION_ANALYSIS_BACKFILL_MAX_AGE_DAYS", 7)
    monkeypatch.setattr(tasks_module.settings, "CONVERSATION_ANALYSIS_BACKFILL_RETRY_DELAY_MINUTES", 45)

    assert await backfill.run([]) is None
    assert backfill.calls == [("get", "ConversationRepository"), ("select", 5, 7, 45)]
