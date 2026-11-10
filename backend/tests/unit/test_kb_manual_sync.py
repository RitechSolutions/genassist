"""A knowledge base's manual sync runs in the background of the API process.

Covers the Redis run store, the heartbeat, the runner, the endpoints and the
batch result's list of knowledge bases that could not be synced.
"""

import asyncio
import json
import threading
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.api.v1.routes import agent_knowledge as knowledge_routes
from app.core.exceptions.error_messages import ErrorKey
from app.core.exceptions.exception_classes import AppException
from app.core.utils import background_tasks
from app.modules.data import manual_sync_runs
from app.modules.data.manual_sync_runs import ManualSyncRunStore
from app.services.agent_knowledge import KnowledgeBaseService
from app.services.datasources import DataSourceService
from app.tasks import kb_batch_tasks, kb_manual_sync

TENANT = "tenant-a"
KB_ID = "kb-1"
ACTIVE_KEY = manual_sync_runs.active_key(TENANT, KB_ID)
RESULT_KEY = manual_sync_runs.result_key(TENANT, KB_ID)


def _run_script(values, expiries, script, keys, args):
    """What the store's Lua scripts do, on plain dicts."""
    active, result = keys
    holder = values.get(active)
    if script == manual_sync_runs.RENEW_OR_RETAKE:
        run_id, ex = args
        if holder not in (run_id, None):
            return 0
        run_has_ended = holder is None and run_id in (values.get(result) or "")
        if run_has_ended:
            return 0
        values[active] = run_id
        expiries[active] = ex
        return 1
    assert script == manual_sync_runs.SAVE_RESULT_UNLESS_SUPERSEDED
    run_id, outcome, ex = args
    if holder not in (run_id, None):
        return 0
    values[result] = outcome
    expiries[result] = ex
    values.pop(active, None)
    return 1


class FakeRedis:
    def __init__(self):
        self.values = {}
        self.expiries = {}

    async def get(self, key):
        return self.values.get(key)

    async def set(self, key, value, ex=None, nx=False):
        if nx and key in self.values:
            return None
        self.values[key] = value
        self.expiries[key] = ex
        return True

    async def eval(self, script, numkeys, *keys_and_args):
        keys, args = keys_and_args[:numkeys], keys_and_args[numkeys:]
        return _run_script(self.values, self.expiries, script, keys, args)


class FakeSyncRedis:
    """The heartbeat thread's blocking client, on a FakeRedis's data."""

    def __init__(self, redis):
        self.values = redis.values
        self.expiries = redis.expiries

    def eval(self, script, numkeys, *keys_and_args):
        keys, args = keys_and_args[:numkeys], keys_and_args[numkeys:]
        return _run_script(self.values, self.expiries, script, keys, args)

    def close(self):
        pass


@pytest.fixture
def redis():
    return FakeRedis()


@pytest.fixture
def store(redis):
    return ManualSyncRunStore(redis)


def _expire(redis, key):
    """What Redis does when a key's time is up."""
    redis.values.pop(key, None)


# --- Run store ---------------------------------------------------------------


@pytest.mark.asyncio
async def test_without_a_run_or_a_result_the_status_is_idle(store):
    assert await store.status(TENANT, KB_ID) == {"status": "idle"}


@pytest.mark.asyncio
async def test_claim_marks_a_run_as_running_for_a_short_renewable_time(store, redis):
    run_id = await store.claim(TENANT, KB_ID)

    assert await store.status(TENANT, KB_ID) == {"status": "running", "run_id": run_id, "previous": None}
    assert redis.expiries[ACTIVE_KEY] == manual_sync_runs.RUNNING_TTL_SECONDS


@pytest.mark.asyncio
async def test_a_second_claim_is_refused_while_a_run_is_in_progress(store):
    run_id = await store.claim(TENANT, KB_ID)

    assert await store.claim(TENANT, KB_ID) is None
    assert await store.claim_or_find_active(TENANT, KB_ID) == (None, run_id)


@pytest.mark.asyncio
async def test_a_claim_whose_reply_was_lost_and_resent_still_counts(redis):
    real_set = redis.set

    async def set_and_lose_the_reply(key, value, ex=None, nx=False):
        await real_set(key, value, ex=ex, nx=nx)
        return None

    redis.set = set_and_lose_the_reply

    run_id = await ManualSyncRunStore(redis).claim(TENANT, KB_ID)

    assert run_id is not None
    assert redis.values[ACTIVE_KEY] == run_id


@pytest.mark.asyncio
async def test_state_is_scoped_by_tenant_and_knowledge_base(store):
    await store.claim(TENANT, KB_ID)

    assert await store.claim("tenant-b", KB_ID) is not None
    assert await store.claim(TENANT, "kb-2") is not None


def test_both_keys_of_a_knowledge_base_share_one_cluster_slot():
    def hash_tag(key):
        return key[key.index("{") + 1 : key.index("}")]

    assert hash_tag(ACTIVE_KEY) == hash_tag(RESULT_KEY) == f"{TENANT}:{KB_ID}"
    assert manual_sync_runs.active_key("", KB_ID).startswith("kb_manual_sync:{master:")


@pytest.mark.asyncio
async def test_a_run_that_ends_while_a_press_is_refused_lets_the_press_start_a_new_one(store, redis):
    first_run_id = await store.claim(TENANT, KB_ID)
    real_status = store.status

    async def status_after_the_run_ended(tenant_id, kb_id):
        await store.finish(tenant_id, kb_id, first_run_id, "succeeded")
        store.status = real_status
        return await real_status(tenant_id, kb_id)

    store.status = status_after_the_run_ended

    run_id, active_run_id = await store.claim_or_find_active(TENANT, KB_ID)

    assert active_run_id is None
    assert run_id not in (None, first_run_id)


@pytest.mark.asyncio
async def test_finish_keeps_the_outcome_and_frees_the_knowledge_base(store, redis):
    run_id = await store.claim(TENANT, KB_ID)

    assert await store.finish(TENANT, KB_ID, run_id, "succeeded", result={"status": "completed"}) is True

    status = await store.status(TENANT, KB_ID)
    assert status["status"] == "succeeded"
    assert status["run_id"] == run_id
    assert status["result"] == {"status": "completed"}
    assert redis.expiries[RESULT_KEY] == manual_sync_runs.RESULT_TTL_SECONDS
    assert await store.claim(TENANT, KB_ID) is not None


@pytest.mark.asyncio
async def test_a_run_whose_mark_expired_still_saves_its_outcome_when_no_newer_run_took_over(store, redis):
    run_id = await store.claim(TENANT, KB_ID)
    _expire(redis, ACTIVE_KEY)

    assert await store.finish(TENANT, KB_ID, run_id, "succeeded") is True
    assert (await store.status(TENANT, KB_ID))["run_id"] == run_id


@pytest.mark.asyncio
async def test_a_run_superseded_by_a_newer_one_cannot_save_its_outcome(store, redis):
    old_run_id = await store.claim(TENANT, KB_ID)
    _expire(redis, ACTIVE_KEY)
    newer_run_id = await store.claim(TENANT, KB_ID)

    assert await store.finish(TENANT, KB_ID, old_run_id, "succeeded") is False

    assert redis.values[ACTIVE_KEY] == newer_run_id
    assert RESULT_KEY not in redis.values


@pytest.mark.asyncio
async def test_saving_an_outcome_twice_gives_the_same_state(store):
    run_id = await store.claim(TENANT, KB_ID)

    await store.finish(TENANT, KB_ID, run_id, "failed", error="Synchronization failed.")
    assert await store.finish(TENANT, KB_ID, run_id, "failed", error="Synchronization failed.") is True

    assert (await store.status(TENANT, KB_ID))["status"] == "failed"


@pytest.mark.asyncio
async def test_while_a_run_is_in_progress_the_status_also_gives_the_last_outcome(store):
    first_run_id = await store.claim(TENANT, KB_ID)
    await store.finish(TENANT, KB_ID, first_run_id, "succeeded", result={"status": "completed"})
    second_run_id = await store.claim(TENANT, KB_ID)

    status = await store.status(TENANT, KB_ID)

    assert status["status"] == "running"
    assert status["run_id"] == second_run_id
    assert status["previous"]["run_id"] == first_run_id
    assert status["previous"]["result"] == {"status": "completed"}


def test_the_stored_result_keeps_only_what_the_page_shows():
    batch_result = {
        "total_kbs": 1,
        "files": [{"file": "a.pdf", "summary": "internal"}],
        "zendesk_sync_results": [
            {
                "kb_id": "kb-1",
                "type": "zendesk",
                "result": {
                    "status": "completed",
                    "articles_added": 2,
                    "articles_updated": 1,
                    "articles_deleted": 0,
                    "datasources_processed": 1,
                    "warnings": ["Error updating article 7: (asyncpg) host db-internal"],
                    "per_kb": [{"kb_id": "kb-1", "status": "error", "reason": "x", "error": "(asyncpg) boom"}],
                },
            }
        ],
        "salesforce_sync_results": [{"result": {"status": "failed", "error": "Knowledge base kb-1 not found"}}],
    }

    summary = manual_sync_runs.result_for_page(batch_result)

    assert summary == {
        "status": "completed",
        "zendesk_sync_results": [
            {
                "result": {
                    "status": "completed",
                    "articles_added": 2,
                    "articles_updated": 1,
                    "articles_deleted": 0,
                    "per_kb": [{"status": "error", "reason": "x"}],
                }
            }
        ],
        "salesforce_sync_results": [{"result": {"status": "failed", "error": "Knowledge base kb-1 not found"}}],
    }
    assert "asyncpg" not in str(summary)


def test_a_sync_result_without_provider_results_gives_empty_lists():
    expected = {"status": "completed", "zendesk_sync_results": [], "salesforce_sync_results": []}

    assert manual_sync_runs.result_for_page(None) == expected
    assert manual_sync_runs.result_for_page({"files": [], "zendesk_sync_results": None}) == expected
    assert manual_sync_runs.result_for_page({"zendesk_sync_results": [{"result": None}]}) == {
        **expected,
        "zendesk_sync_results": [{"result": None}],
    }


# --- Heartbeat ---------------------------------------------------------------


@pytest.mark.asyncio
async def test_the_heartbeat_renews_its_mark_and_takes_back_an_expired_one(store, redis):
    run_id = await store.claim(TENANT, KB_ID)
    client = FakeSyncRedis(redis)
    redis.expiries[ACTIVE_KEY] = 1

    assert kb_manual_sync._keep_running_mark(client, TENANT, KB_ID, run_id) is True
    assert redis.expiries[ACTIVE_KEY] == manual_sync_runs.RUNNING_TTL_SECONDS

    _expire(redis, ACTIVE_KEY)
    assert kb_manual_sync._keep_running_mark(client, TENANT, KB_ID, run_id) is True
    assert redis.values[ACTIVE_KEY] == run_id


@pytest.mark.asyncio
async def test_the_heartbeat_never_marks_a_run_running_again_once_its_outcome_is_saved(store, redis):
    run_id = await store.claim(TENANT, KB_ID)
    await store.finish(TENANT, KB_ID, run_id, "succeeded")

    assert kb_manual_sync._keep_running_mark(FakeSyncRedis(redis), TENANT, KB_ID, run_id) is False

    assert ACTIVE_KEY not in redis.values
    assert (await store.status(TENANT, KB_ID))["status"] == "succeeded"


@pytest.mark.asyncio
async def test_the_heartbeat_leaves_a_knowledge_base_that_a_newer_run_holds(store, redis):
    run_id = await store.claim(TENANT, KB_ID)
    _expire(redis, ACTIVE_KEY)
    newer_run_id = await store.claim(TENANT, KB_ID)

    assert kb_manual_sync._keep_running_mark(FakeSyncRedis(redis), TENANT, KB_ID, run_id) is False
    assert redis.values[ACTIVE_KEY] == newer_run_id


@pytest.mark.asyncio
async def test_the_heartbeat_thread_reports_a_newer_run_once(monkeypatch, redis):
    monkeypatch.setattr(kb_manual_sync, "_open_heartbeat_redis", lambda: FakeSyncRedis(redis))
    monkeypatch.setattr(manual_sync_runs, "HEARTBEAT_SECONDS", 0.01)
    redis.values[ACTIVE_KEY] = "newer-run"
    superseded = threading.Event()
    calls = []

    def on_superseded():
        calls.append(1)
        superseded.set()

    stop_heartbeat = kb_manual_sync._start_heartbeat(TENANT, KB_ID, "older-run", on_superseded)

    assert superseded.wait(timeout=2)
    stop_heartbeat.set()
    await asyncio.sleep(0.05)
    assert calls == [1]
    assert redis.values[ACTIVE_KEY] == "newer-run"


@pytest.mark.asyncio
async def test_a_stopped_heartbeat_no_longer_touches_the_mark(monkeypatch, redis, store):
    monkeypatch.setattr(kb_manual_sync, "_open_heartbeat_redis", lambda: FakeSyncRedis(redis))
    monkeypatch.setattr(manual_sync_runs, "HEARTBEAT_SECONDS", 0.01)
    run_id = await store.claim(TENANT, KB_ID)
    stop_heartbeat = kb_manual_sync._start_heartbeat(TENANT, KB_ID, run_id, lambda: None)

    stop_heartbeat.set()
    await asyncio.sleep(0.03)
    _expire(redis, ACTIVE_KEY)
    await asyncio.sleep(0.05)

    assert ACTIVE_KEY not in redis.values


@pytest.mark.asyncio
async def test_the_heartbeat_stops_renewing_after_the_hold_limit(monkeypatch, redis, store):
    monkeypatch.setattr(kb_manual_sync, "_open_heartbeat_redis", lambda: FakeSyncRedis(redis))
    monkeypatch.setattr(manual_sync_runs, "HEARTBEAT_SECONDS", 0.01)
    monkeypatch.setattr(manual_sync_runs, "MARK_HOLD_LIMIT_SECONDS", 0.03)
    run_id = await store.claim(TENANT, KB_ID)
    superseded = []
    stop_heartbeat = kb_manual_sync._start_heartbeat(TENANT, KB_ID, run_id, lambda: superseded.append(1))

    await asyncio.sleep(0.1)
    _expire(redis, ACTIVE_KEY)
    await asyncio.sleep(0.05)

    assert ACTIVE_KEY not in redis.values
    assert superseded == []
    stop_heartbeat.set()


# --- Runner ------------------------------------------------------------------


@pytest.fixture
def runner_env(monkeypatch):
    """The runner with the sync itself and the heartbeat thread replaced."""
    env = SimpleNamespace(
        sync_calls=[],
        outcome={"status": "success", "result": {}},
        before_sync_returns=None,
        sync_started=asyncio.Event(),
        stop_heartbeat=None,
        on_superseded=None,
    )

    async def run_task_for_tenant(task_func, task_name, tenant_id, **kwargs):
        env.sync_calls.append((task_func, tenant_id, kwargs))
        env.sync_started.set()
        if env.outcome == "never ends":
            await asyncio.Event().wait()
        if env.before_sync_returns:
            env.before_sync_returns()
        return env.outcome

    def start_heartbeat(tenant_id, kb_id, run_id, on_superseded):
        env.stop_heartbeat = threading.Event()
        env.on_superseded = on_superseded
        return env.stop_heartbeat

    monkeypatch.setattr(kb_manual_sync, "run_task_for_tenant", run_task_for_tenant)
    monkeypatch.setattr(kb_manual_sync, "_start_heartbeat", start_heartbeat)
    return env


async def _run(store, run_id):
    await kb_manual_sync._run_manual_sync(store, TENANT, KB_ID, run_id)


@pytest.mark.asyncio
async def test_the_sync_runs_in_its_tenant_and_its_result_is_kept(store, runner_env):
    runner_env.outcome = {
        "status": "success",
        "result": {"zendesk_sync_results": [{"result": {"articles_added": 2}}], "files": ["a.pdf"]},
    }
    run_id = await store.claim(TENANT, KB_ID)

    await _run(store, run_id)

    assert runner_env.sync_calls == [(kb_batch_tasks.batch_process_files_kb_async, TENANT, {"kb_id": KB_ID})]
    status = await store.status(TENANT, KB_ID)
    assert status["status"] == "succeeded"
    assert status["result"] == {
        "status": "completed",
        "zendesk_sync_results": [{"result": {"articles_added": 2}}],
        "salesforce_sync_results": [],
    }
    assert runner_env.stop_heartbeat.is_set()


@pytest.mark.asyncio
async def test_a_failed_sync_is_kept_without_its_internal_reason(store, redis, runner_env):
    runner_env.outcome = {"status": "failed", "error": "(asyncpg) INSERT INTO chunks ... host db-internal"}
    run_id = await store.claim(TENANT, KB_ID)

    await _run(store, run_id)

    status = await store.status(TENANT, KB_ID)
    assert status["status"] == "failed"
    assert status["error"] == kb_manual_sync.SYNC_FAILED_ERROR
    assert status["result"] is None
    assert "asyncpg" not in redis.values[RESULT_KEY]
    assert await store.claim(TENANT, KB_ID) is not None


@pytest.mark.asyncio
async def test_a_sync_that_could_not_sync_its_knowledge_base_is_kept_as_failed(store, runner_env):
    runner_env.outcome = {"status": "success", "result": {"kbs_not_synced": [KB_ID], "zendesk_sync_results": []}}
    run_id = await store.claim(TENANT, KB_ID)

    await _run(store, run_id)

    status = await store.status(TENANT, KB_ID)
    assert status["status"] == "failed"
    assert status["error"] == kb_manual_sync.SYNC_FAILED_ERROR


@pytest.mark.asyncio
async def test_a_run_superseded_by_a_newer_run_stops_and_saves_nothing(store, redis, runner_env):
    runner_env.outcome = "never ends"
    run_id = await store.claim(TENANT, KB_ID)
    running = asyncio.create_task(_run(store, run_id))
    await runner_env.sync_started.wait()
    _expire(redis, ACTIVE_KEY)
    newer_run_id = await store.claim(TENANT, KB_ID)

    runner_env.on_superseded()
    await asyncio.wait_for(running, timeout=1)

    assert redis.values[ACTIVE_KEY] == newer_run_id
    assert RESULT_KEY not in redis.values
    assert runner_env.stop_heartbeat.is_set()


@pytest.mark.asyncio
async def test_a_server_shutdown_stops_the_sync_without_saving_an_outcome(store, redis, runner_env):
    runner_env.outcome = "never ends"
    run_id = await store.claim(TENANT, KB_ID)
    running = asyncio.create_task(_run(store, run_id))
    await runner_env.sync_started.wait()

    running.cancel()
    with pytest.raises(asyncio.CancelledError):
        await running

    assert RESULT_KEY not in redis.values
    assert runner_env.stop_heartbeat.is_set()


@pytest.mark.asyncio
async def test_a_sync_whose_mark_expired_still_keeps_its_result(store, redis, runner_env):
    run_id = await store.claim(TENANT, KB_ID)
    runner_env.before_sync_returns = lambda: _expire(redis, ACTIVE_KEY)

    await _run(store, run_id)

    assert (await store.status(TENANT, KB_ID))["status"] == "succeeded"


@pytest.mark.asyncio
async def test_saving_the_outcome_is_retried_once_after_a_redis_error(store, runner_env):
    run_id = await store.claim(TENANT, KB_ID)
    real_finish = store.finish
    attempts = []

    async def finish_failing_once(*args, **kwargs):
        attempts.append(1)
        if len(attempts) == 1:
            raise ConnectionError("redis blip")
        return await real_finish(*args, **kwargs)

    store.finish = finish_failing_once

    await _run(store, run_id)

    assert len(attempts) == 2
    assert (await store.status(TENANT, KB_ID))["status"] == "succeeded"


@pytest.mark.asyncio
async def test_start_answers_at_once_and_the_sync_finishes_in_the_background(store, runner_env):
    started = await kb_manual_sync.start_manual_sync(store, TENANT, KB_ID)

    assert started["status"] == "started"
    assert (await store.status(TENANT, KB_ID))["status"] == "running"
    await asyncio.gather(*background_tasks._TASKS)
    status = await store.status(TENANT, KB_ID)
    assert status["status"] == "succeeded"
    assert status["run_id"] == started["run_id"]


@pytest.mark.asyncio
async def test_start_refuses_a_second_sync_while_one_is_in_progress(store, runner_env):
    runner_env.outcome = "never ends"
    first = await kb_manual_sync.start_manual_sync(store, TENANT, KB_ID)

    second = await kb_manual_sync.start_manual_sync(store, TENANT, KB_ID)

    assert second == {"status": "already_running", "run_id": first["run_id"]}
    assert len(background_tasks._TASKS) == 1
    await background_tasks.drain(timeout=0.01)


@pytest.mark.asyncio
async def test_a_shutdown_waits_briefly_for_the_sync_then_stops_it_without_saving(store, redis, runner_env):
    runner_env.outcome = "never ends"
    await kb_manual_sync.start_manual_sync(store, TENANT, KB_ID)
    await runner_env.sync_started.wait()

    await background_tasks.drain(timeout=0.01)

    assert background_tasks._TASKS == set()
    assert RESULT_KEY not in redis.values
    assert runner_env.stop_heartbeat.is_set()


@pytest.mark.asyncio
async def test_start_that_can_neither_claim_nor_find_a_run_asks_to_try_again(runner_env):
    class UndecidedStore:
        async def claim_or_find_active(self, tenant_id, kb_id):
            return None, None

    response = await kb_manual_sync.start_manual_sync(UndecidedStore(), TENANT, KB_ID)

    assert response == {"status": "error", "message": kb_manual_sync.SYNC_NOT_STARTED_MESSAGE}
    assert runner_env.sync_calls == []


# --- Endpoints ---------------------------------------------------------------


class FakeKnowledgeService:
    def __init__(self, missing=False):
        self.missing = missing

    async def get_by_id(self, kb_id):
        if self.missing:
            raise AppException(status_code=404, error_key=ErrorKey.KB_NOT_FOUND)
        return SimpleNamespace(id=kb_id)


@pytest.fixture
def route_env(monkeypatch, redis, runner_env):
    monkeypatch.setattr(knowledge_routes.injector, "get", lambda _cls: redis)
    monkeypatch.setattr(knowledge_routes, "get_tenant_context", lambda: TENANT)
    return SimpleNamespace(redis=redis, runner=runner_env)


async def _press_sync_now(kb_id, service=None):
    return await knowledge_routes.summarize_files_from_azure(
        kb_id=kb_id, knowledge_service=service or FakeKnowledgeService()
    )


async def _read_status(kb_id, service=None):
    return await knowledge_routes.get_manual_sync_status(
        kb_id=kb_id, knowledge_service=service or FakeKnowledgeService()
    )


@pytest.mark.asyncio
async def test_sync_now_starts_the_sync_and_the_status_follows_it(route_env):
    kb_id = uuid4()

    response = await _press_sync_now(kb_id)

    assert response["status"] == "started"
    assert (await _read_status(kb_id))["status"] == "running"
    await asyncio.gather(*background_tasks._TASKS)
    status = await _read_status(kb_id)
    assert status["status"] == "succeeded"
    assert status["run_id"] == response["run_id"]
    assert route_env.runner.sync_calls[0][2] == {"kb_id": str(kb_id)}


@pytest.mark.asyncio
async def test_sync_now_without_a_knowledge_base_id_is_an_error(route_env):
    response = await _press_sync_now(None)

    assert response == {"status": "error", "message": "kb_id is required"}
    assert route_env.runner.sync_calls == []


@pytest.mark.asyncio
async def test_a_knowledge_base_that_does_not_exist_is_refused_before_anything_starts(route_env):
    with pytest.raises(AppException) as refused:
        await _press_sync_now(uuid4(), FakeKnowledgeService(missing=True))

    assert refused.value.status_code == 404
    assert route_env.redis.values == {}
    assert route_env.runner.sync_calls == []


@pytest.mark.asyncio
async def test_the_status_of_a_knowledge_base_that_does_not_exist_is_refused(route_env):
    with pytest.raises(AppException) as refused:
        await _read_status(uuid4(), FakeKnowledgeService(missing=True))

    assert refused.value.status_code == 404


# --- Knowledge bases that could not be synced -------------------------------


class FakeBatchKnowledgeService:
    def __init__(self, kb_item=None):
        self.kb_item = kb_item

    async def get_by_id(self, kb_id):
        if self.kb_item is None:
            raise AppException(status_code=404, error_key=ErrorKey.KB_NOT_FOUND)
        return self.kb_item


class FakeDataSourceService:
    async def get_by_id(self, ds_id, decrypt=False):
        return None


def _kb_item(kb_type):
    return SimpleNamespace(
        id=KB_ID, type=kb_type, sync_schedule=None, extra_metadata={}, rag_config={}, sync_source_id="ds-1"
    )


@pytest.fixture
def batch_env(monkeypatch):
    services = {DataSourceService: FakeDataSourceService(), KnowledgeBaseService: FakeBatchKnowledgeService()}
    monkeypatch.setattr(kb_batch_tasks.injector, "get", lambda cls: services.get(cls))
    return services


@pytest.mark.asyncio
async def test_a_knowledge_base_that_cannot_be_loaded_is_listed_as_not_synced(batch_env):
    result = await kb_batch_tasks.batch_process_files_kb_async(kb_id=KB_ID)

    assert result["kbs_not_synced"] == [KB_ID]


@pytest.mark.asyncio
async def test_an_article_import_that_raises_is_listed_as_not_synced(batch_env, monkeypatch):
    batch_env[KnowledgeBaseService] = FakeBatchKnowledgeService(_kb_item("zendesk"))

    async def failing_import(kb_id, sync_now):
        raise RuntimeError("database gone")

    monkeypatch.setattr(kb_batch_tasks, "import_zendesk_articles_to_kb_async", failing_import)

    result = await kb_batch_tasks.batch_process_files_kb_async(kb_id=KB_ID)

    assert result["kbs_not_synced"] == [KB_ID]
    assert result["zendesk_sync_results"] == []


@pytest.mark.asyncio
async def test_a_file_knowledge_base_without_its_datasource_is_listed_as_not_synced(batch_env):
    batch_env[KnowledgeBaseService] = FakeBatchKnowledgeService(_kb_item("s3"))

    result = await kb_batch_tasks.batch_process_files_kb_async(kb_id=KB_ID)

    assert result["kbs_not_synced"] == [KB_ID]
    assert result["failed_kb"] == 1


@pytest.mark.asyncio
async def test_an_article_import_that_runs_lists_nothing_as_not_synced(batch_env, monkeypatch):
    batch_env[KnowledgeBaseService] = FakeBatchKnowledgeService(_kb_item("zendesk"))
    import_result = {"status": "completed", "articles_added": 1}

    async def working_import(kb_id, sync_now):
        return import_result

    monkeypatch.setattr(kb_batch_tasks, "import_zendesk_articles_to_kb_async", working_import)

    result = await kb_batch_tasks.batch_process_files_kb_async(kb_id=KB_ID)

    assert result["kbs_not_synced"] == []
    assert result["zendesk_sync_results"] == [{"kb_id": KB_ID, "type": "zendesk", "result": import_result}]


@pytest.mark.asyncio
async def test_the_scheduled_batch_without_a_knowledge_base_lists_nothing_as_not_synced(batch_env):
    result = await kb_batch_tasks.batch_process_files_kb_async()

    assert result["kbs_not_synced"] == []
    assert json.loads(json.dumps(result))["total_kbs"] == 0
