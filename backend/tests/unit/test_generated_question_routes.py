"""The endpoints that estimate, start and report a question-writing run."""
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.api.v1.routes import test_cases as routes
from app.core.exceptions.error_messages import ErrorKey
from app.core.exceptions.exception_classes import AppException
from app.schemas.test_suite import WriteQuestionsRequest
from tests.unit.test_generated_question_job import FakeRedis

TENANT = "tenant-a"


class Services:
    """Suite, knowledge base and provider lookups that answer, or raise for an unknown id."""

    def __init__(self, missing=()):
        self.missing = set(missing)

    async def _lookup(self, kind, value):
        if kind in self.missing:
            raise AppException(status_code=404, error_key=ErrorKey.NOT_FOUND)
        return SimpleNamespace(id=value)

    async def get_suite(self, suite_id):
        return await self._lookup("suite", suite_id)

    async def get_by_id(self, value):
        return await self._lookup("other", value)


@pytest.fixture
def started(monkeypatch):
    redis, sent = FakeRedis(), []
    rag = SimpleNamespace(get_document_ids=lambda _kb: _ids(["a", "b", "c"]))
    monkeypatch.setattr(routes, "get_tenant_context", lambda: TENANT)
    monkeypatch.setattr(routes.injector, "get", lambda cls: rag if cls is routes.AgentRAGServiceManager else redis)
    monkeypatch.setattr(routes.write_dataset_questions_task, "delay", lambda *args: sent.append(args))
    return sent


async def _ids(values):
    return values


def request(sample_size=None):
    return WriteQuestionsRequest(knowledge_base_id=uuid4(), llm_provider_id=uuid4(), sample_size=sample_size)


@pytest.mark.asyncio
async def test_the_estimate_counts_the_stored_articles(started):
    estimate = await routes.estimate_cases_from_knowledge_base(uuid4(), uuid4(), 2, Services(), Services())
    assert estimate == {"articles": 2, "writing_calls": 2, "judging_calls_at_most": 20}


@pytest.mark.asyncio
async def test_a_start_sends_one_task_and_a_second_start_returns_the_run_in_progress(started):
    suite_id, data = uuid4(), request(sample_size=5)
    first = await routes.write_cases_from_knowledge_base(suite_id, data, Services(), Services(), Services())
    second = await routes.write_cases_from_knowledge_base(suite_id, data, Services(), Services(), Services())
    assert first["status"] == "queued" and second["run_id"] == first["run_id"]
    assert started == [(first["run_id"], TENANT, str(suite_id), str(data.knowledge_base_id), str(data.llm_provider_id), 5)]
    status = await routes.get_cases_from_knowledge_base_status(suite_id, Services())
    assert status["run_id"] == first["run_id"]


@pytest.mark.parametrize("missing", ["suite", "other"])
@pytest.mark.asyncio
async def test_an_unknown_dataset_knowledge_base_or_model_starts_nothing(started, missing):
    with pytest.raises(AppException):
        await routes.write_cases_from_knowledge_base(uuid4(), request(), Services([missing]), Services([missing]), Services([missing]))
    assert started == []


def test_a_sample_size_must_be_at_least_one():
    with pytest.raises(ValueError):
        request(sample_size=0)


@pytest.mark.asyncio
async def test_a_run_that_cannot_be_sent_to_the_worker_frees_the_dataset(started, monkeypatch):
    def broker_down(*_args):
        raise ConnectionError("broker down")

    monkeypatch.setattr(routes.write_dataset_questions_task, "delay", broker_down)
    suite_id = uuid4()
    with pytest.raises(ConnectionError):
        await routes.write_cases_from_knowledge_base(suite_id, request(), Services(), Services(), Services())
    status = await routes.get_cases_from_knowledge_base_status(suite_id, Services())
    assert (status["status"], status["error"]) == ("failed", "The run did not start. Try again.")
    monkeypatch.setattr(routes.write_dataset_questions_task, "delay", lambda *args: started.append(args))
    retried = await routes.write_cases_from_knowledge_base(suite_id, request(), Services(), Services(), Services())
    assert retried["status"] == "queued" and len(started) == 1
