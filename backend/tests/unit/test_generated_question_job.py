"""A background run fills a dataset with questions written from a knowledge base."""
import asyncio
import json
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.modules.data.providers.models import StoredDocument
from app.services import generated_question_job as job_module
from app.services import generated_question_runs as runs
from app.services.generated_question_job import (
    GeneratedQuestionJob,
    QuestionRunRequest,
    model_calls,
    reply_text,
)
from app.services.generated_question_runs import GeneratedQuestionRunStore
from app.services.generated_questions import WRITE_PROMPT

TENANT = "tenant-a"
ARTICLES = {
    "KB:kb-1#article_1": ("Lock the bike", "Push the ring lock on the back wheel down until it clicks."),
    "KB:kb-1#article_2": ("Return the bike", "Park it at any station and wait for the green light on the dock."),
    "KB:kb-1#article_3": ("Pay for a ride", "The saved bank card is charged when the ride ends."),
}
MESSAGES = {
    "KB:kb-1#article_1": "My bike rolled away outside the shop, how do I stop that?",
    "KB:kb-1#article_2": "I am done riding, where does the bike go now?",
    "KB:kb-1#article_3": "Nobody asked me for money yet, is that normal?",
}


class FakeRedis:
    def __init__(self):
        self.values = {}
        self.expiries = {}

    async def set(self, key, value, ex=None, nx=False):
        if nx and key in self.values:
            return None
        self.values[key] = value
        self.expiries[key] = ex
        return True

    async def get(self, key):
        return self.values.get(key)

    async def delete(self, key):
        self.values.pop(key, None)

    async def expire(self, key, seconds):
        self.expiries[key] = seconds


def documents():
    return [StoredDocument(id=doc_id, title=title, content=f"{title}\n{text}") for doc_id, (title, text) in ARTICLES.items()]


class World:
    """The services a run uses, replaced by stand-ins that record what they are asked."""

    def __init__(self, stored=None, existing=(), failing=(), copying=False):
        self.stored = documents() if stored is None else stored
        self.copying = copying
        self.on_model_call = None
        self.cases = [SimpleNamespace(input_data={"message": message}) for message in existing]
        self.failing = set(failing)
        self.added = []
        self.commits = 0
        self.store = GeneratedQuestionRunStore(FakeRedis())
        self.suite_id = uuid4()

    async def list_cases_for_suite(self, _suite_id):
        return list(self.cases)

    async def add_case(self, data):
        self.added.append(data)

    async def get_by_id(self, kb_id):
        return SimpleNamespace(id=kb_id)

    async def get_documents(self, _knowledge_base):
        return self.stored

    async def search(self, _knowledge_bases, query, limit=5):
        source = next(doc_id for doc_id, message in MESSAGES.items() if message == query)
        return [SimpleNamespace(id=source)]

    async def get_model(self, _provider_id):
        return SimpleNamespace(ainvoke=self.ainvoke)

    async def ainvoke(self, messages):
        system, human = messages[0].content, messages[1].content
        assert system == WRITE_PROMPT
        doc_id = next(doc_id for doc_id, (title, _text) in ARTICLES.items() if title in human)
        if self.on_model_call:
            await self.on_model_call(doc_id)
        if doc_id in self.failing:
            raise RuntimeError("model unavailable")
        message = f"Where can I read about {ARTICLES[doc_id][0]}?" if self.copying else MESSAGES[doc_id]
        return SimpleNamespace(content=json.dumps({"messages": [message]}))

    async def commit(self):
        self.commits += 1

    def job(self):
        return GeneratedQuestionJob(self, self, self, self, self.store, self.commit)

    def request(self, run_id, sample_size=None):
        return QuestionRunRequest(TENANT, self.suite_id, uuid4(), uuid4(), run_id, sample_size)

    async def run(self, sample_size=None):
        run_id = await self.store.claim(TENANT, str(self.suite_id), "kb-1")
        await self.job().run(self.request(run_id, sample_size))
        return await self.store.status(TENANT, str(self.suite_id))


class TestRunStore:
    @pytest.mark.asyncio
    async def test_a_dataset_holds_one_run_at_a_time(self):
        store = GeneratedQuestionRunStore(FakeRedis())
        run_id = await store.claim(TENANT, "suite-1", "kb-1")
        assert run_id and await store.claim(TENANT, "suite-1", "kb-1") is None
        assert await store.claim(TENANT, "suite-2", "kb-1")

    @pytest.mark.asyncio
    async def test_a_dataset_never_filled_is_idle(self):
        assert await GeneratedQuestionRunStore(FakeRedis()).status(TENANT, "suite-1") == {"status": "idle"}

    @pytest.mark.asyncio
    async def test_a_claimed_run_is_queued_and_holds_the_dataset_long_enough_to_wait_its_turn(self):
        redis = FakeRedis()
        store = GeneratedQuestionRunStore(redis)
        await store.claim(TENANT, "suite-1", "kb-1")
        assert (await store.status(TENANT, "suite-1"))["status"] == "queued"
        assert redis.expiries[runs._key(TENANT, "suite-1", "active")] == runs.QUEUED_TTL_SECONDS

    @pytest.mark.asyncio
    async def test_counts_are_saved_and_the_outcome_frees_the_dataset(self):
        redis = FakeRedis()
        store = GeneratedQuestionRunStore(redis)
        run_id = await store.claim(TENANT, "suite-1", "kb-1")
        assert await store.report(TENANT, "suite-1", run_id, {"articles_total": 3, "articles_done": 1})
        assert redis.expiries[runs._key(TENANT, "suite-1", "active")] == runs.RUNNING_TTL_SECONDS
        running = await store.status(TENANT, "suite-1")
        assert (running["status"], running["articles_done"], running["knowledge_base_id"]) == ("running", 1, "kb-1")
        await store.finish(TENANT, "suite-1", run_id, runs.STATUS_SUCCEEDED)
        assert (await store.status(TENANT, "suite-1"))["status"] == "succeeded"
        assert await store.claim(TENANT, "suite-1", "kb-1")

    @pytest.mark.asyncio
    async def test_a_run_whose_worker_is_gone_reads_as_failed(self):
        redis = FakeRedis()
        store = GeneratedQuestionRunStore(redis)
        run_id = await store.claim(TENANT, "suite-1", "kb-1")
        await store.report(TENANT, "suite-1", run_id, {})
        await redis.delete(runs._key(TENANT, "suite-1", "active"))
        status = await store.status(TENANT, "suite-1")
        assert (status["status"], status["error"]) == ("failed", runs.RUN_LOST_ERROR)

    @pytest.mark.asyncio
    async def test_a_queued_run_that_never_started_reads_as_not_started(self):
        redis = FakeRedis()
        store = GeneratedQuestionRunStore(redis)
        await store.claim(TENANT, "suite-1", "kb-1")
        await redis.delete(runs._key(TENANT, "suite-1", "active"))
        status = await store.status(TENANT, "suite-1")
        assert (status["status"], status["error"]) == ("failed", runs.NOT_STARTED_ERROR)

    @pytest.mark.asyncio
    async def test_a_run_that_lost_its_mark_cannot_take_it_back(self):
        redis = FakeRedis()
        store = GeneratedQuestionRunStore(redis)
        run_id = await store.claim(TENANT, "suite-1", "kb-1")
        await redis.delete(runs._key(TENANT, "suite-1", "active"))
        assert not await store.report(TENANT, "suite-1", run_id, {"articles_done": 1})
        assert (await store.status(TENANT, "suite-1"))["status"] == "failed"

    @pytest.mark.asyncio
    async def test_a_run_replaced_by_a_newer_one_is_told_to_stop(self):
        redis = FakeRedis()
        store = GeneratedQuestionRunStore(redis)
        older = await store.claim(TENANT, "suite-1", "kb-1")
        await redis.delete(runs._key(TENANT, "suite-1", "active"))
        newer = await store.claim(TENANT, "suite-1", "kb-1")
        assert not await store.report(TENANT, "suite-1", older, {"articles_done": 2})
        await store.finish(TENANT, "suite-1", older, runs.STATUS_FAILED)
        assert (await store.status(TENANT, "suite-1"))["run_id"] == newer

    @pytest.mark.asyncio
    async def test_finishing_leaves_a_newer_runs_mark_alone(self):
        redis = FakeRedis()
        store = GeneratedQuestionRunStore(redis)
        older = await store.claim(TENANT, "suite-1", "kb-1")
        await redis.set(runs._key(TENANT, "suite-1", "active"), "newer-run")
        await store.finish(TENANT, "suite-1", older, runs.STATUS_FAILED)
        assert await redis.get(runs._key(TENANT, "suite-1", "active")) == "newer-run"


class TestRun:
    @pytest.mark.asyncio
    async def test_each_kept_message_becomes_a_one_turn_conversation_tagged_generated(self):
        world = World()
        status = await world.run()
        assert [case.input_data["message"] for case in world.added] == list(MESSAGES.values())
        assert [case.expected_articles for case in world.added] == [["Lock the bike"], ["Return the bike"], ["Pay for a ride"]]
        assert all(case.tags == ["generated"] and case.turn_index == 0 and case.suite_id == world.suite_id for case in world.added)
        assert len({case.source_conversation_id for case in world.added}) == 3
        assert (status["status"], status["articles_total"], status["articles_done"], status["messages_added"]) == ("succeeded", 3, 3, 3)

    @pytest.mark.asyncio
    async def test_a_message_already_in_the_dataset_is_not_added_again(self):
        world = World(existing=["  i am DONE riding, where does the bike go now? "])
        status = await world.run()
        assert len(world.added) == 2
        assert (status["messages_added"], status["messages_dropped"]) == (2, 1)

    @pytest.mark.asyncio
    async def test_a_run_that_waited_past_its_mark_adds_nothing(self):
        world = World()
        run_id = await world.store.claim(TENANT, str(world.suite_id), "kb-1")
        await world.store._redis.delete(runs._key(TENANT, str(world.suite_id), "active"))
        await world.job().run(world.request(run_id))
        status = await world.store.status(TENANT, str(world.suite_id))
        assert (status["status"], world.added) == ("failed", [])

    @pytest.mark.asyncio
    async def test_a_run_where_the_first_articles_all_fail_ends_as_failed_with_the_reason(self, monkeypatch):
        monkeypatch.setattr(job_module, "CONCURRENT_ARTICLES", 2)
        world = World(failing=list(ARTICLES))
        status = await world.run()
        assert (status["status"], status["error"]) == ("failed", job_module.NOTHING_ANSWERED_ERROR)
        assert (status["articles_failed"], status["messages_added"]) == (2, 0)

    @pytest.mark.asyncio
    async def test_a_failure_on_one_article_does_not_stop_the_others(self):
        world = World(failing=["KB:kb-1#article_2"])
        status = await world.run()
        assert len(world.added) == 2
        assert (status["status"], status["articles_done"], status["articles_failed"]) == ("succeeded", 2, 1)

    @pytest.mark.asyncio
    async def test_a_knowledge_base_without_stored_articles_fails_with_the_reason(self):
        status = await World(stored=[]).run()
        assert (status["status"], status["error"]) == ("failed", job_module.NO_ARTICLES_ERROR)

    @pytest.mark.asyncio
    async def test_a_sample_uses_that_many_articles(self):
        world = World()
        status = await world.run(sample_size=2)
        assert (status["articles_total"], len(world.added)) == (2, 2)

    @pytest.mark.asyncio
    async def test_progress_is_saved_after_each_batch(self, monkeypatch):
        monkeypatch.setattr(job_module, "CONCURRENT_ARTICLES", 1)
        world = World()
        await world.run()
        assert world.commits == 4

    @pytest.mark.asyncio
    async def test_no_new_article_is_started_once_the_time_is_up(self, monkeypatch):
        monkeypatch.setattr(job_module, "TIME_LIMIT_SECONDS", job_module.STOP_MARGIN_SECONDS)
        world = World()
        status = await world.run()
        assert (status["status"], status["error"]) == ("stopped", job_module.TIME_LIMIT_ERROR)
        assert (status["articles_done"], world.added) == (0, [])

    @pytest.mark.asyncio
    async def test_a_run_cut_off_by_the_worker_records_what_it_added(self, monkeypatch):
        monkeypatch.setattr(job_module, "CONCURRENT_ARTICLES", 1)
        world = World()

        async def cut_off_at_the_second_article(doc_id):
            if doc_id == "KB:kb-1#article_2":
                raise asyncio.CancelledError()

        world.on_model_call = cut_off_at_the_second_article
        with pytest.raises(asyncio.CancelledError):
            await world.run()
        status = await world.store.status(TENANT, str(world.suite_id))
        assert (status["status"], status["error"]) == ("stopped", job_module.TIME_LIMIT_ERROR)
        assert (status["articles_done"], status["messages_added"], len(world.added)) == (1, 1, 1)

    @pytest.mark.asyncio
    async def test_a_run_that_loses_the_dataset_during_a_batch_saves_nothing_of_it(self):
        world = World()
        newer = {}

        async def newer_run_takes_the_dataset(_doc_id):
            if not newer:
                await world.store._redis.delete(runs._key(TENANT, str(world.suite_id), "active"))
                newer["run_id"] = await world.store.claim(TENANT, str(world.suite_id), "kb-1")

        world.on_model_call = newer_run_takes_the_dataset
        await world.run()
        status = await world.store.status(TENANT, str(world.suite_id))
        assert world.added == []
        assert (status["run_id"], status["status"]) == (newer["run_id"], "queued")

    @pytest.mark.asyncio
    async def test_a_first_batch_whose_messages_were_all_dropped_still_succeeds(self):
        status = await World(copying=True).run()
        assert (status["status"], status["error"]) == ("succeeded", None)
        assert (status["articles_done"], status["messages_dropped"], status["messages_added"]) == (3, 3, 0)

    @pytest.mark.asyncio
    async def test_an_unexpected_error_ends_the_run_as_failed(self):
        world = World()

        async def broken(_suite_id):
            raise RuntimeError("database gone")

        world.list_cases_for_suite = broken
        status = await world.run()
        assert (status["status"], status["error"]) == ("failed", job_module.RUN_FAILED_ERROR)


class TestEstimateAndReply:
    def test_the_estimate_counts_one_writing_call_per_article_and_the_most_judging_calls(self):
        assert model_calls(90) == {"articles": 90, "writing_calls": 90, "judging_calls_at_most": 900}
        assert model_calls(90, sample_size=10)["articles"] == 10
        assert model_calls(5, sample_size=10)["articles"] == 5

    def test_a_reply_is_read_as_text_whatever_its_form(self):
        assert reply_text(SimpleNamespace(content="plain")) == "plain"
        assert reply_text(SimpleNamespace(content=[{"type": "text", "text": "in "}, {"type": "text", "text": "parts"}])) == "in parts"
