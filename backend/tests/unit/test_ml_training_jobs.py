"""
Training runs as a background job with a core cap and a search-size limit.

Covers: counting a hyperparameter search's fits before it starts, refusing
one above ML_HPO_MAX_FITS, capping CV workers and estimator threads at
ML_TRAINING_MAX_CORES, the Redis job store, the /workflows test endpoints
queueing a job for Train Model, and the Celery job runner.
"""

import asyncio
import json
import threading
import time
from types import SimpleNamespace
from unittest.mock import MagicMock

import numpy as np
import pandas as pd
import pytest

from app.api.v1.routes import workflows as workflow_routes
from app.core.config.settings import settings
from app.core.exceptions.error_messages import ErrorKey
from app.core.exceptions.exception_classes import AppException
from app.modules.workflow import training_jobs
from app.modules.workflow.engine.nodes.ml import hyperparameter_optimization as hpo_module
from app.modules.workflow.engine.nodes.ml import model_registry, training_progress
from app.tasks import ml_training_job_tasks

# The test routes take the request first; no X-Keepalive header runs them inline.
NO_KEEPALIVE = SimpleNamespace(headers={})


class FakeRedis:
    def __init__(self):
        self.values = {}

    async def get(self, key):
        return self.values.get(key)

    async def set(self, key, value, ex=None, nx=False):
        if nx and key in self.values:
            return None
        self.values[key] = value
        self.expiries = {**getattr(self, "expiries", {}), key: ex}
        return True

    async def eval(self, script, numkeys, key, *args):
        if script == training_jobs._REPLACE_IF_UNCHANGED:
            expected, new_value, _ex = args
            if self.values.get(key) != expected:
                return None
            self.values[key] = new_value
            return True
        # _SET_IF_STATUS: write the job only if its stored status is allowed.
        assert script == training_jobs._SET_IF_STATUS
        new_value, _ex, *allowed = args
        raw = self.values.get(key)
        if raw is None or json.loads(raw)["status"] not in allowed:
            return None
        self.values[key] = new_value
        return 1

    async def aclose(self):
        self.closed = True


class FakeSyncRedis:
    """The heartbeat thread's blocking client, reading and writing a FakeRedis's values."""

    def __init__(self, values):
        self.values = values

    def get(self, key):
        return self.values.get(key)

    def set(self, key, value, ex=None):
        self.values[key] = value

    def close(self):
        pass


# --- Search size -------------------------------------------------------------


def test_default_xgboost_grid_search_is_729_fits():
    plan = hpo_module.plan_search("xgboost", {}, "grid_search", {})

    assert plan == {"candidates": 243, "cv_folds": 3, "fits": 729}


def test_fixed_parameters_are_left_out_of_the_count():
    plan = hpo_module.plan_search("xgboost", {"max_depth": 4, "subsample": 0.8}, "grid_search", {"cvFolds": 5})

    assert plan == {"candidates": 27, "cv_folds": 5, "fits": 135}


def test_random_search_never_counts_more_candidates_than_the_grid_holds():
    plan = hpo_module.plan_search("knn", {}, "random_search", {"nIter": 150, "cvFolds": 2})

    grid_size = len(hpo_module.ParameterGrid(hpo_module._build_param_grid(hpo_module.get_space("knn"), 8)))
    assert plan["candidates"] == min(150, grid_size)
    assert plan["fits"] == plan["candidates"] * 2


def test_bayesian_optimization_counts_trials_times_folds():
    plan = hpo_module.plan_search("random_forest", {}, "bayesian_optimization", {"nTrials": 40, "cvFolds": 4})

    assert plan == {"candidates": 40, "cv_folds": 4, "fits": 160}


@pytest.mark.parametrize(
    "model_type, method",
    [("xgboost", "none"), ("linear_regression", "grid_search"), ("xgboost", "not_a_method")],
)
def test_no_plan_when_no_search_runs(model_type, method):
    assert hpo_module.plan_search(model_type, {}, method, {}) is None


def test_search_above_the_limit_is_refused_with_its_size(monkeypatch):
    monkeypatch.setattr(settings, "ML_HPO_MAX_FITS", 500)

    with pytest.raises(AppException) as exc_info:
        hpo_module.check_search_size("xgboost", {}, "grid_search", {})

    assert exc_info.value.error_key == ErrorKey.ML_TRAINING_SEARCH_TOO_LARGE
    assert exc_info.value.status_code == 400
    assert exc_info.value.error_detail.startswith(
        "This grid search would train 729 models (243 parameter combinations x 3 folds), more than the limit of 500."
    )


def test_search_at_the_limit_is_allowed(monkeypatch):
    monkeypatch.setattr(settings, "ML_HPO_MAX_FITS", 729)

    assert hpo_module.check_search_size("xgboost", {}, "grid_search", {})["fits"] == 729


def test_default_limit_allows_the_729_fit_search():
    assert hpo_module.check_search_size("xgboost", {}, "grid_search", {})["fits"] == 729


def test_optimize_refuses_before_fitting(monkeypatch):
    monkeypatch.setattr(settings, "ML_HPO_MAX_FITS", 10)
    grid_search = MagicMock()
    monkeypatch.setattr(hpo_module, "GridSearchCV", grid_search)
    X = pd.DataFrame({"a": np.arange(30.0)})

    with pytest.raises(AppException):
        hpo_module.optimize_hyperparameters(
            "decision_tree", False, X, X["a"], "grid_search", {}, {}, is_time_based=False
        )

    grid_search.assert_not_called()


# --- Core cap ----------------------------------------------------------------


@pytest.mark.parametrize(
    "params, expected",
    [
        ({}, 2),
        ({"n_jobs": -1}, 2),
        ({"n_jobs": 16}, 2),
        ({"n_jobs": 1}, 1),
        ({"n_jobs": None}, 2),
        ({"n_jobs": True}, 2),
    ],
)
def test_estimator_threads_are_capped(params, expected):
    assert model_registry.cap_estimator_threads("xgboost", params, 2)["n_jobs"] == expected


def test_catboost_cap_uses_thread_count():
    assert model_registry.cap_estimator_threads("catboost", {}, 3) == {"thread_count": 3}


def test_single_threaded_models_are_unchanged():
    assert model_registry.cap_estimator_threads("svm", {"C": 1.0}, 2) == {"C": 1.0}


def test_search_uses_capped_workers_and_single_threaded_estimators(monkeypatch):
    monkeypatch.setattr(settings, "ML_TRAINING_MAX_CORES", 2)
    created = {}
    real_grid_search = hpo_module.GridSearchCV

    def recording_grid_search(estimator, param_grid, **kwargs):
        created["n_jobs"] = kwargs["n_jobs"]
        created["estimator_n_jobs"] = estimator.get_params()["n_jobs"]
        return real_grid_search(estimator, param_grid, **kwargs)

    monkeypatch.setattr(hpo_module, "GridSearchCV", recording_grid_search)
    rng = np.random.default_rng(0)
    X = pd.DataFrame({"a": rng.normal(size=40), "b": rng.normal(size=40)})
    y = X["a"] * 2

    result = hpo_module.optimize_hyperparameters(
        "random_forest",
        False,
        X,
        y,
        "grid_search",
        {"n_estimators": 10, "max_depth": 3, "min_samples_split": 2, "max_features": "sqrt"},
        {"cvFolds": 2},
        is_time_based=False,
    )

    assert created == {"n_jobs": 2, "estimator_n_jobs": 1}
    assert result["search_metadata"]["candidates_evaluated"] == 6


# --- Job store ---------------------------------------------------------------


@pytest.mark.asyncio
async def test_job_store_round_trip_is_scoped_by_tenant():
    store = training_jobs.TrainingJobStore(FakeRedis())
    job, _ = await store.start("tenant-a", "user-1", "workflow")

    assert job["status"] == training_jobs.STATUS_QUEUED
    assert (await store.get("tenant-a", job["job_id"]))["user_id"] == "user-1"
    assert await store.get("tenant-b", job["job_id"]) is None

    await store.update("tenant-a", job["job_id"], status=training_jobs.STATUS_RUNNING)
    assert (await store.get("tenant-a", job["job_id"]))["status"] == training_jobs.STATUS_RUNNING


def test_public_view_hides_owner_and_reports_a_lost_worker():
    job = {"job_id": "j", "status": "running", "user_id": "u", "heartbeat": time.time() - 600, "error": None}

    view = training_jobs.public_view(job)

    assert "user_id" not in view and "heartbeat" not in view
    assert view["status"] == training_jobs.STATUS_FAILED
    assert view["error"] == training_jobs.WORKER_LOST_ERROR


def test_public_view_keeps_a_live_running_job():
    job = {"job_id": "j", "status": "running", "heartbeat": time.time()}

    assert training_jobs.public_view(job)["status"] == training_jobs.STATUS_RUNNING


def test_train_model_nodes_are_found_in_dicts_and_models():
    nodes = [
        {"type": "chatInputNode", "data": {}},
        {"type": "trainModelNode", "data": {"modelType": "xgboost"}},
        SimpleNamespace(type="trainModelNode", data={"modelType": "knn"}),
    ]

    assert training_jobs.train_model_nodes(nodes) == [{"modelType": "xgboost"}, {"modelType": "knn"}]


def test_templated_training_config_is_left_to_the_node():
    training_jobs.check_training_config({"modelType": "{{source.model}}", "hyperparameterOptimization": "grid_search"})
    training_jobs.check_training_config({"modelType": "xgboost", "optimizationConfig": "{{config}}"})


# --- Endpoints ---------------------------------------------------------------


@pytest.fixture
def route_env(monkeypatch):
    redis = FakeRedis()
    delay = MagicMock()
    monkeypatch.setattr(workflow_routes.injector, "get", lambda _cls: redis)
    monkeypatch.setattr(workflow_routes, "get_tenant_context", lambda: "tenant-a")
    monkeypatch.setattr(workflow_routes, "get_current_user_id", lambda: "user-1")
    monkeypatch.setattr(ml_training_job_tasks.run_training_job_task, "delay", delay)
    return SimpleNamespace(redis=redis, delay=delay)


TRAIN_NODE_CONFIG = {
    "name": "m",
    "modelType": "xgboost",
    "fileUrl": "data.csv",
    "targetColumn": "y",
    "featureColumns": ["a"],
    "hyperparameterOptimization": "grid_search",
}


@pytest.mark.asyncio
async def test_test_node_queues_train_model_and_returns_a_job_id(route_env):
    response = await workflow_routes.test_individual_node(
        NO_KEEPALIVE,
        {"node_type": "trainModelNode", "node_config": TRAIN_NODE_CONFIG, "input_data": {}}
    )

    assert response.status_code == 202
    sent_job_id, tenant_id, payload = route_env.delay.call_args.args
    assert tenant_id == "tenant-a"
    assert payload["workflow_config"]["nodes"][0]["type"] == "trainModelNode"
    assert payload["start_node_id"] == payload["workflow_config"]["nodes"][0]["id"]

    job = await workflow_routes.get_training_job(sent_job_id)
    assert job["status"] == training_jobs.STATUS_QUEUED


@pytest.mark.asyncio
async def test_test_node_runs_train_model_under_the_canvas_node_id(route_env):
    # The node marks the model it registers with its id; a retest must reuse it
    # to update that model instead of failing with ML_MODEL_NAME_EXISTS (68072).
    await workflow_routes.test_individual_node(
        NO_KEEPALIVE,
        {
            "node_type": "trainModelNode",
            "node_config": TRAIN_NODE_CONFIG,
            "input_data": {},
            "node_id": "node-abc",
        },
    )

    payload = route_env.delay.call_args.args[2]
    assert payload["workflow_config"]["nodes"][0]["id"] == "node-abc"
    assert payload["start_node_id"] == "node-abc"
    assert payload["workflow_config"]["id"].startswith("test-trainModelNode-")


@pytest.mark.parametrize("node_id", [None, "", "   ", 123, "x" * 201, "a\nb", "<b>x</b>"])
def test_unusable_test_node_ids_fall_back_to_the_test_id(node_id):
    assert workflow_routes._test_node_id("trainModelNode", node_id, "test-id") == "test-id"


def test_a_canvas_uuid_is_kept():
    node_id = "3f2b6c1e-8a4d-4f1b-9c2e-7d5a6b4c3e21"
    assert workflow_routes._test_node_id("trainModelNode", f" {node_id} ", "test-id") == node_id


def test_other_node_types_keep_a_throwaway_test_id():
    assert workflow_routes._test_node_id("agentNode", "node-abc", "test-id") == "test-id"


@pytest.mark.asyncio
async def test_test_workflow_with_a_train_model_node_is_queued(route_env):
    workflow = {
        "id": "wf-1",
        "name": "training",
        "nodes": [
            {"id": "source", "type": "trainDataSourceNode", "data": {}},
            {"id": "train", "type": "trainModelNode", "data": TRAIN_NODE_CONFIG},
        ],
        "edges": [],
    }

    response = await workflow_routes.test_workflow(
        NO_KEEPALIVE,
        {"input_data": {"message": "go"}, "workflow": workflow}, workflow_id=None, workflow_service=MagicMock()
    )

    assert response.status_code == 202
    payload = route_env.delay.call_args.args[2]
    assert payload["input_data"] == {"message": "go"}
    assert payload["workflow_id"] == "wf-1"
    # The job runs the turn with sub-agent routing, as the endpoint would.
    assert payload["kind"] == "workflow"


@pytest.mark.asyncio
async def test_oversized_search_is_refused_before_queueing(route_env, monkeypatch):
    monkeypatch.setattr(settings, "ML_HPO_MAX_FITS", 100)

    with pytest.raises(AppException) as exc_info:
        await workflow_routes.test_individual_node(
            NO_KEEPALIVE,
            {"node_type": "trainModelNode", "node_config": TRAIN_NODE_CONFIG}
        )

    assert exc_info.value.error_key == ErrorKey.ML_TRAINING_SEARCH_TOO_LARGE
    route_env.delay.assert_not_called()
    assert route_env.redis.values == {}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "method, optimization_config",
    [
        ("grid_search", {"cvFolds": 1}),
        ("grid_search", {"cvFolds": 11}),
        ("bayesian_optimization", {"nTrials": 201}),
    ],
)
async def test_out_of_range_search_settings_are_refused_before_queueing(route_env, method, optimization_config):
    """TM-17: refused with 400 by API, before a job is queued."""
    node_config = {**TRAIN_NODE_CONFIG, "hyperparameterOptimization": method, "optimizationConfig": optimization_config}

    with pytest.raises(AppException) as exc_info:
        await workflow_routes.test_individual_node(
            NO_KEEPALIVE, {"node_type": "trainModelNode", "node_config": node_config}
        )

    assert exc_info.value.status_code == 400
    route_env.delay.assert_not_called()
    assert route_env.redis.values == {}


@pytest.mark.asyncio
async def test_out_of_range_folds_in_a_workflow_test_are_refused_before_queueing(route_env):
    node_config = {**TRAIN_NODE_CONFIG, "optimizationConfig": {"cvFolds": 1}}
    workflow = {"name": "wf", "nodes": [{"id": "n1", "type": "trainModelNode", "data": node_config}], "edges": []}

    with pytest.raises(AppException) as exc_info:
        await workflow_routes.test_workflow(
            NO_KEEPALIVE, {"workflow": workflow, "input_data": {"message": "go"}}, workflow_service=MagicMock()
        )

    assert exc_info.value.status_code == 400
    route_env.delay.assert_not_called()


def test_templated_search_settings_are_left_to_the_node():
    training_jobs.check_training_config(
        {**TRAIN_NODE_CONFIG, "optimizationConfig": {"cvFolds": "{{inputs.folds}}"}}
    )


@pytest.mark.parametrize(
    "optimization_config",
    [
        {"nTrials": 0},  # left over from Bayesian; the node still refuses it
        {"gridPoints": 1},
        {"timeoutSeconds": 0},
    ],
)
def test_values_the_node_would_refuse_are_refused_before_queueing(optimization_config):
    node_config = {**TRAIN_NODE_CONFIG, "hyperparameterOptimization": "random_search", "optimizationConfig": optimization_config}
    with pytest.raises(AppException) as exc_info:
        training_jobs.check_training_config(node_config)
    assert exc_info.value.status_code == 400


def test_a_malformed_scoring_value_is_left_to_the_node():
    # Only the counts are checked before queueing; the node reports the rest.
    training_jobs.check_training_config({**TRAIN_NODE_CONFIG, "optimizationConfig": {"scoring": ["accuracy"]}})


@pytest.mark.asyncio
async def test_a_job_is_only_visible_to_the_user_who_started_it(route_env, monkeypatch):
    await workflow_routes.test_individual_node(
        NO_KEEPALIVE,
        {"node_type": "trainModelNode", "node_config": TRAIN_NODE_CONFIG}
    )
    job_id = route_env.delay.call_args.args[0]
    monkeypatch.setattr(workflow_routes, "get_current_user_id", lambda: "user-2")

    with pytest.raises(AppException) as exc_info:
        await workflow_routes.get_training_job(job_id)

    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_a_caller_without_a_user_id_cannot_start_or_read_jobs(route_env, monkeypatch):
    await workflow_routes.test_individual_node(
        NO_KEEPALIVE,
        {"node_type": "trainModelNode", "node_config": TRAIN_NODE_CONFIG}
    )
    job_id = route_env.delay.call_args.args[0]
    monkeypatch.setattr(workflow_routes, "get_current_user_id", lambda: None)

    with pytest.raises(AppException) as start_exc:
        await workflow_routes.test_individual_node(
            NO_KEEPALIVE,
            {"node_type": "trainModelNode", "node_config": TRAIN_NODE_CONFIG}
        )
    with pytest.raises(AppException) as read_exc:
        await workflow_routes.get_training_job(job_id)

    assert start_exc.value.error_key == ErrorKey.ML_TRAINING_JOB_NEEDS_USER
    assert start_exc.value.status_code == 403
    assert read_exc.value.error_key == ErrorKey.ML_TRAINING_JOB_NEEDS_USER
    assert route_env.delay.call_count == 1


@pytest.mark.asyncio
async def test_two_concurrent_requests_queue_one_job(route_env):
    request = {"node_type": "trainModelNode", "node_config": TRAIN_NODE_CONFIG}
    real_get = route_env.redis.get

    async def slow_get(key):
        # Let the other request run between this request's reads and writes.
        await asyncio.sleep(0)
        return await real_get(key)

    route_env.redis.get = slow_get

    results = await asyncio.gather(
        workflow_routes.test_individual_node(NO_KEEPALIVE, dict(request)),
        workflow_routes.test_individual_node(NO_KEEPALIVE, dict(request)),
        return_exceptions=True,
    )

    assert route_env.delay.call_count == 1
    assert sorted(type(r).__name__ for r in results) == ["AppException", "JSONResponse"]


@pytest.mark.asyncio
async def test_finished_job_slot_is_taken_by_exactly_one_new_job(route_env):
    store = training_jobs.TrainingJobStore(route_env.redis)
    first, _ = await store.start("tenant-a", "user-1", "node")
    await store.update("tenant-a", first["job_id"], status=training_jobs.STATUS_SUCCEEDED)

    real_get = route_env.redis.get

    async def slow_get(key):
        await asyncio.sleep(0)
        return await real_get(key)

    route_env.redis.get = slow_get
    results = await asyncio.gather(
        store.start("tenant-a", "user-1", "node"), store.start("tenant-a", "user-1", "node")
    )

    started = [job for job, running in results if job is not None]
    refused = [running for job, running in results if running is not None]
    assert len(started) == 1 and len(refused) == 1
    assert refused[0]["job_id"] == started[0]["job_id"]


@pytest.mark.asyncio
async def test_the_active_job_can_be_found_and_cancelled(route_env):
    await workflow_routes.test_individual_node(
        NO_KEEPALIVE,
        {"node_type": "trainModelNode", "node_config": TRAIN_NODE_CONFIG}
    )
    job_id = route_env.delay.call_args.args[0]

    active = await workflow_routes.get_active_training_job()
    assert active["job_id"] == job_id

    cancelled = await workflow_routes.cancel_training_job(job_id)
    assert cancelled["status"] == training_jobs.STATUS_CANCELLED

    with pytest.raises(AppException) as exc_info:
        await workflow_routes.get_active_training_job()
    assert exc_info.value.status_code == 404
    # The slot is free again.
    response = await workflow_routes.test_individual_node(
        NO_KEEPALIVE,
        {"node_type": "trainModelNode", "node_config": TRAIN_NODE_CONFIG}
    )
    assert response.status_code == 202


@pytest.mark.asyncio
async def test_another_user_cannot_cancel_a_job(route_env, monkeypatch):
    await workflow_routes.test_individual_node(
        NO_KEEPALIVE,
        {"node_type": "trainModelNode", "node_config": TRAIN_NODE_CONFIG}
    )
    job_id = route_env.delay.call_args.args[0]
    monkeypatch.setattr(workflow_routes, "get_current_user_id", lambda: "user-2")

    with pytest.raises(AppException) as exc_info:
        await workflow_routes.cancel_training_job(job_id)

    assert exc_info.value.status_code == 404
    store = training_jobs.TrainingJobStore(route_env.redis)
    assert (await store.get("tenant-a", job_id))["status"] == training_jobs.STATUS_QUEUED


@pytest.mark.asyncio
async def test_a_user_runs_one_training_job_at_a_time(route_env):
    request = {"node_type": "trainModelNode", "node_config": TRAIN_NODE_CONFIG}
    await workflow_routes.test_individual_node(NO_KEEPALIVE, request)
    first_job_id = route_env.delay.call_args.args[0]

    with pytest.raises(AppException) as exc_info:
        await workflow_routes.test_individual_node(NO_KEEPALIVE, request)

    assert exc_info.value.status_code == 409
    assert exc_info.value.error_key == ErrorKey.ML_TRAINING_JOB_ALREADY_RUNNING
    assert route_env.delay.call_count == 1

    # Once the first job has finished, the next test is queued.
    store = training_jobs.TrainingJobStore(route_env.redis)
    await store.update("tenant-a", first_job_id, status=training_jobs.STATUS_SUCCEEDED)
    response = await workflow_routes.test_individual_node(NO_KEEPALIVE, request)
    assert response.status_code == 202
    assert route_env.delay.call_count == 2


@pytest.mark.asyncio
async def test_a_failed_enqueue_marks_the_job_failed(route_env):
    route_env.delay.side_effect = ConnectionError("broker down")

    with pytest.raises(workflow_routes.HTTPException) as exc_info:
        await workflow_routes.test_individual_node(
            NO_KEEPALIVE,
            {"node_type": "trainModelNode", "node_config": TRAIN_NODE_CONFIG}
        )

    assert exc_info.value.status_code == 503
    [stored] = [await training_jobs.TrainingJobStore(route_env.redis).get("tenant-a", key.rsplit(":", 1)[1])
                for key in route_env.redis.values if key.startswith("ml_training_job:")]
    assert stored["status"] == training_jobs.STATUS_FAILED
    # A failed enqueue doesn't block the user's next test.
    assert await training_jobs.TrainingJobStore(route_env.redis).active_job("tenant-a", "user-1") is None


# --- Job runner --------------------------------------------------------------


class _FakeState:
    def format_state_as_response(self):
        return {"output": {"success": True, "metrics": {"r2": 0.9}}}


def _fake_engine(behaviour):
    class FakeEngine:
        workflow_id = "wf-1"

        def __init__(self, config):
            self.config = config

        async def execute_from_node(self, **kwargs):
            return await behaviour(kwargs)

    return FakeEngine


@pytest.fixture
def runner_env(monkeypatch):
    redis = FakeRedis()
    monkeypatch.setattr(ml_training_job_tasks, "_open_job_redis", lambda: redis)
    monkeypatch.setattr(ml_training_job_tasks, "_open_heartbeat_redis", lambda: FakeSyncRedis(redis.values))
    monkeypatch.setattr(ml_training_job_tasks, "get_tenant_context", lambda: "tenant-a")
    return training_jobs.TrainingJobStore(redis)


@pytest.mark.asyncio
async def test_runner_records_progress_and_the_result(runner_env, monkeypatch):
    from app.modules.workflow.engine import workflow_engine

    seen = {}

    async def behaviour(kwargs):
        training_progress.report("training", "Training 729 models", 30)
        seen["kwargs"] = kwargs
        return _FakeState()

    monkeypatch.setattr(workflow_engine, "WorkflowEngine", _fake_engine(behaviour))
    job, _ = await runner_env.start("tenant-a", "user-1", "node")

    await ml_training_job_tasks.run_training_job_async(
        job["job_id"], {"workflow_config": {"id": "t", "nodes": [], "edges": []}, "start_node_id": "t"}
    )

    stored = await runner_env.get("tenant-a", job["job_id"])
    assert stored["status"] == training_jobs.STATUS_SUCCEEDED
    assert stored["result"] == {"output": {"success": True, "metrics": {"r2": 0.9}}}
    assert stored["progress"]["percent"] == 100
    assert seen["kwargs"]["start_node_id"] == "t"
    # Recorded inline: deferred capture tasks would be cancelled with the task's event loop.
    assert seen["kwargs"]["usage_context"].defer_capture is False
    # Each job closes its own client: the next task runs in a new event loop.
    assert runner_env._redis.closed


@pytest.mark.asyncio
async def test_runner_records_a_failure(runner_env, monkeypatch):
    from app.modules.workflow.engine import workflow_engine

    async def behaviour(_kwargs):
        training_progress.report("training", "Training", 30)
        raise AppException(ErrorKey.ML_TRAINING_SEARCH_TOO_LARGE, 400, "Search too large")

    monkeypatch.setattr(workflow_engine, "WorkflowEngine", _fake_engine(behaviour))
    job, _ = await runner_env.start("tenant-a", "user-1", "node")

    await ml_training_job_tasks.run_training_job_async(job["job_id"], {"workflow_config": {}})

    stored = await runner_env.get("tenant-a", job["job_id"])
    assert stored["status"] == training_jobs.STATUS_FAILED
    assert stored["error"] == "Search too large"
    assert stored["progress"]["stage"] == "training"


class _ResponseState:
    def __init__(self, response):
        self.response = response

    def format_state_as_response(self):
        return self.response


@pytest.mark.asyncio
async def test_a_run_whose_train_model_node_failed_fails_the_job(runner_env, monkeypatch):
    """TM-17: the run returns normally, but its Train Model node failed."""
    from app.modules.workflow.engine import workflow_engine

    response = {
        "status": "failed",
        "has_failures": True,
        "failed_nodes": [
            {"node_id": "n1", "name": "Train", "type": "trainModelNode", "error": "CV Folds must be 2 or more."}
        ],
        "output": None,
    }

    async def behaviour(_kwargs):
        return _ResponseState(response)

    monkeypatch.setattr(workflow_engine, "WorkflowEngine", _fake_engine(behaviour))
    job, _ = await runner_env.start("tenant-a", "user-1", "node")

    await ml_training_job_tasks.run_training_job_async(job["job_id"], {"workflow_config": {}})

    stored = await runner_env.get("tenant-a", job["job_id"])
    assert stored["status"] == training_jobs.STATUS_FAILED
    assert stored["error"] == "CV Folds must be 2 or more."
    # The run's response is kept, so its failed nodes can still be shown.
    assert stored["result"] == response


def test_run_failure_reads_the_runs_status():
    assert training_jobs.run_failure({"status": "success", "failed_nodes": []}) is None
    assert training_jobs.run_failure({"output": {"success": True}}) is None
    assert training_jobs.run_failure(None) is None
    # A partial run whose Train Model node failed still fails the training job.
    assert training_jobs.run_failure(
        {"status": "partial", "failed_nodes": [{"type": "trainModelNode", "error": "boom"}]}
    ) == "boom"
    # A failed run without a failing Train Model node reports the first node's error.
    assert training_jobs.run_failure(
        {"status": "failed", "failed_nodes": [{"type": "agentNode", "error": "no key"}]}
    ) == "no key"
    assert training_jobs.run_failure({"status": "failed", "failed_nodes": []}) == "The test run failed."
    # A broken leftover Train Model next to one that trained doesn't fail the job,
    # as it doesn't fail an ML pipeline run.
    assert training_jobs.run_failure(
        {
            "status": "partial",
            "failed_nodes": [{"type": "trainModelNode", "error": "leftover"}],
            "output": {"success": True, "model_file_path": "ml_models/m.pkl"},
        }
    ) is None
    # Even when the run's status is failed (e.g. the Chat Output after the
    # broken node never ran), another Train Model's model makes it a success.
    assert training_jobs.run_failure(
        {
            "status": "failed",
            "failed_nodes": [{"type": "trainModelNode", "error": "leftover"}],
            "output": None,
            "state": {
                "nodeExecutionStatus": {
                    "b": {
                        "type": "trainModelNode",
                        "status": "success",
                        "output": {"success": True, "model_file_path": "ml_models/b.pkl"},
                    }
                }
            },
        }
    ) is None
    # Another node failing in a run that still answered leaves the job succeeded.
    assert training_jobs.run_failure(
        {"status": "partial", "failed_nodes": [{"type": "slackNode", "error": "x"}]}
    ) is None


@pytest.mark.asyncio
async def test_runner_heartbeat_publishes_progress_while_training(runner_env, monkeypatch):
    from app.modules.workflow.engine import workflow_engine

    monkeypatch.setattr(training_jobs, "HEARTBEAT_SECONDS", 0.01)
    snapshots = []
    job, _ = await runner_env.start("tenant-a", "user-1", "node")

    async def behaviour(_kwargs):
        training_progress.report("training", "Training 729 models", 30)
        # Blocks the event loop, as loading a large file does: the heartbeat
        # runs in its own thread, so it still publishes.
        time.sleep(0.1)
        snapshots.append(await runner_env.get("tenant-a", job["job_id"]))
        return _FakeState()

    monkeypatch.setattr(workflow_engine, "WorkflowEngine", _fake_engine(behaviour))

    await ml_training_job_tasks.run_training_job_async(job["job_id"], {"workflow_config": {}})

    assert snapshots[0]["status"] == training_jobs.STATUS_RUNNING
    assert snapshots[0]["progress"]["message"] == "Training 729 models"


@pytest.mark.asyncio
async def test_runner_skips_a_job_that_already_ran(runner_env, monkeypatch):
    from app.modules.workflow.engine import workflow_engine

    engine = MagicMock()
    monkeypatch.setattr(workflow_engine, "WorkflowEngine", engine)
    job, _ = await runner_env.start("tenant-a", "user-1", "node")
    await runner_env.update("tenant-a", job["job_id"], status=training_jobs.STATUS_RUNNING)

    await ml_training_job_tasks.run_training_job_async(job["job_id"], {"workflow_config": {}})

    engine.assert_not_called()


@pytest.mark.asyncio
async def test_a_job_no_worker_started_in_time_is_failed_and_skipped(runner_env, monkeypatch):
    from app.modules.workflow.engine import workflow_engine

    job, _ = await runner_env.start("tenant-a", "user-1", "node")
    job["heartbeat"] -= training_jobs.QUEUED_TIMEOUT_SECONDS + 1
    await runner_env._save("tenant-a", job)

    view = training_jobs.public_view(await runner_env.get("tenant-a", job["job_id"]))
    assert view["status"] == training_jobs.STATUS_FAILED
    assert view["error"] == training_jobs.NOT_STARTED_ERROR
    assert await runner_env.active_job("tenant-a", "user-1") is None

    engine = MagicMock()
    monkeypatch.setattr(workflow_engine, "WorkflowEngine", engine)
    await ml_training_job_tasks.run_training_job_async(job["job_id"], {"workflow_config": {}})
    engine.assert_not_called()


def test_progress_report_without_a_job_does_nothing():
    training_progress.report("training", "no job", 50)


# --- Train Model node --------------------------------------------------------


@pytest.mark.asyncio
async def test_train_model_node_refuses_an_oversized_search_before_loading_data(monkeypatch):
    from app.modules.workflow.engine.nodes.ml import ml_utils
    from app.modules.workflow.engine.nodes.ml.train_model_node import TrainModelNode
    from app.modules.workflow.engine.workflow_state import WorkflowState

    monkeypatch.setattr(settings, "ML_HPO_MAX_FITS", 100)
    load_csv_file = MagicMock()
    monkeypatch.setattr(ml_utils, "load_csv_file", load_csv_file)
    node = TrainModelNode(node_id="train", node_config={}, state=WorkflowState(workflow={}))

    with pytest.raises(AppException) as exc_info:
        await node.process(TRAIN_NODE_CONFIG)

    assert exc_info.value.error_key == ErrorKey.ML_TRAINING_SEARCH_TOO_LARGE
    load_csv_file.assert_not_called()


# --- Review fixes: cancel, timeout, sub-agent routing, core caps -------------


@pytest.mark.asyncio
async def test_a_cancelled_running_job_stops_its_run(runner_env, monkeypatch):
    from app.modules.workflow.engine import workflow_engine

    monkeypatch.setattr(training_jobs, "HEARTBEAT_SECONDS", 0.01)
    stop_worker = MagicMock()
    monkeypatch.setattr(ml_training_job_tasks, "_stop_worker", stop_worker)
    job, _ = await runner_env.start("tenant-a", "user-1", "node")
    reached_end = []

    async def behaviour(_kwargs):
        await runner_env.cancel("tenant-a", job["job_id"])
        await asyncio.sleep(5)
        reached_end.append(True)
        return _FakeState()

    monkeypatch.setattr(workflow_engine, "WorkflowEngine", _fake_engine(behaviour))

    await asyncio.wait_for(ml_training_job_tasks.run_training_job_async(job["job_id"], {"workflow_config": {}}), 2)

    stored = await runner_env.get("tenant-a", job["job_id"])
    assert stored["status"] == training_jobs.STATUS_CANCELLED
    assert reached_end == []
    # No fit was running, so the worker keeps going.
    stop_worker.assert_not_called()


@pytest.mark.asyncio
async def test_a_timeout_during_a_fit_marks_the_job_failed_and_stops_the_worker(runner_env, monkeypatch):
    from app.modules.workflow.engine import workflow_engine

    stop_worker = MagicMock()
    monkeypatch.setattr(ml_training_job_tasks, "_stop_worker", stop_worker)
    job, _ = await runner_env.start("tenant-a", "user-1", "node")

    release_fit = threading.Event()

    def fit():
        # A fit in a worker thread: cancelling the job's coroutine doesn't stop it.
        with training_progress.fitting():
            release_fit.wait(5)

    async def behaviour(_kwargs):
        await asyncio.to_thread(fit)
        return _FakeState()

    monkeypatch.setattr(workflow_engine, "WorkflowEngine", _fake_engine(behaviour))

    try:
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(
                ml_training_job_tasks.run_training_job_async(job["job_id"], {"workflow_config": {}}), 0.2
            )
    finally:
        release_fit.set()

    stored = await runner_env.get("tenant-a", job["job_id"])
    assert stored["status"] == training_jobs.STATUS_FAILED
    assert "did not finish" in stored["error"]
    stop_worker.assert_called_once()


@pytest.mark.asyncio
async def test_a_timeout_with_no_fit_running_keeps_the_worker(runner_env, monkeypatch):
    from app.modules.workflow.engine import workflow_engine

    stop_worker = MagicMock()
    monkeypatch.setattr(ml_training_job_tasks, "_stop_worker", stop_worker)
    job, _ = await runner_env.start("tenant-a", "user-1", "node")

    async def behaviour(_kwargs):
        await asyncio.sleep(5)
        return _FakeState()

    monkeypatch.setattr(workflow_engine, "WorkflowEngine", _fake_engine(behaviour))

    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(
            ml_training_job_tasks.run_training_job_async(job["job_id"], {"workflow_config": {}}), 0.1
        )

    assert (await runner_env.get("tenant-a", job["job_id"]))["status"] == training_jobs.STATUS_FAILED
    stop_worker.assert_not_called()


@pytest.mark.asyncio
async def test_a_workflow_job_runs_the_turn_like_the_test_endpoint(runner_env, monkeypatch):
    from app.modules.workflow import test_runs
    from app.modules.workflow.engine import workflow_engine

    calls = {}

    async def fake_run_workflow_test(engine, owner_id, input_data, thread_id, start_node_id, usage_context):
        calls.update(owner_id=owner_id, input_data=input_data, thread_id=thread_id, start_node_id=start_node_id)
        return {"output": "routed"}

    monkeypatch.setattr(test_runs, "run_workflow_test", fake_run_workflow_test)
    monkeypatch.setattr(workflow_engine, "WorkflowEngine", _fake_engine(None))
    job, _ = await runner_env.start("tenant-a", "user-1", "workflow")

    await ml_training_job_tasks.run_training_job_async(
        job["job_id"],
        {
            "kind": "workflow",
            "workflow_config": {"id": "wf-1", "nodes": [], "edges": []},
            "input_data": {"message": "hi", "thread_id": "t-1"},
            "thread_id": "t-1",
            "start_node_id": None,
        },
    )

    stored = await runner_env.get("tenant-a", job["job_id"])
    assert stored["status"] == training_jobs.STATUS_SUCCEEDED
    assert stored["result"] == {"output": "routed"}
    assert calls == {"owner_id": "wf-1", "input_data": {"message": "hi", "thread_id": "t-1"}, "thread_id": "t-1", "start_node_id": None}


@pytest.mark.asyncio
async def test_run_workflow_test_passes_registry_managed_for_a_supplied_thread():
    from app.modules.workflow import test_runs

    seen = {}

    class Engine:
        workflow = {"nodes": []}
        workflow_id = "wf-1"

        async def execute_from_node(self, **kwargs):
            seen.update(kwargs)
            return _FakeState()

    await test_runs.run_workflow_test(Engine(), "wf-1", {"thread_id": "t-1"}, "t-1", None, MagicMock())
    assert seen["registry_managed"] is True

    await test_runs.run_workflow_test(Engine(), "wf-1", {}, "t-2", None, MagicMock())
    assert seen["registry_managed"] is False


def test_cv_workers_get_one_native_thread(monkeypatch):
    from sklearn.utils.parallel import Parallel, delayed
    from threadpoolctl import threadpool_info

    def worker_threads(_):
        return max((info["num_threads"] for info in threadpool_info()), default=1)

    with hpo_module._single_threaded_cv_workers():
        threads = Parallel(n_jobs=2)(delayed(worker_threads)(i) for i in range(2))

    assert threads == [1, 1]


def test_overlapping_native_limits_are_restored_by_the_last_fit(monkeypatch):
    events = []

    class FakeLimiter:
        def restore_original_limits(self):
            events.append("restore")

    def fake_limits(limits):
        events.append(("limit", limits))
        return FakeLimiter()

    monkeypatch.setattr(hpo_module, "threadpool_limits", fake_limits)
    monkeypatch.setattr(settings, "ML_TRAINING_MAX_CORES", 2)

    first = hpo_module.native_thread_limit()
    second = hpo_module.native_thread_limit()
    first.__enter__()
    second.__enter__()
    first.__exit__(None, None, None)
    assert events == [("limit", 2)]  # still limited for the second fit
    second.__exit__(None, None, None)
    assert events == [("limit", 2), "restore"]


def test_native_limit_is_only_set_inside_a_training_job(monkeypatch):
    from app.modules.workflow.engine.nodes.ml.train_model_node import TrainModelNode

    limit = MagicMock()
    monkeypatch.setattr(hpo_module, "native_thread_limit", limit)

    assert TrainModelNode._run_with_core_limit(lambda: "fit") == "fit"
    limit.assert_not_called()

    with training_progress.reporting_to(lambda _update: None):
        assert TrainModelNode._run_with_core_limit(lambda: "fit") == "fit"
    limit.assert_called_once()


# --- Second review: status races, slot lifetime, reachability, thread caps ---


@pytest.mark.asyncio
async def test_the_workers_result_does_not_overwrite_a_cancel():
    store = training_jobs.TrainingJobStore(FakeRedis())
    job, _ = await store.start("tenant-a", "user-1", "node")
    await store.update("tenant-a", job["job_id"], status=training_jobs.STATUS_RUNNING)
    await store.cancel("tenant-a", job["job_id"])

    written = await store.update(
        "tenant-a",
        job["job_id"],
        expect=(training_jobs.STATUS_RUNNING,),
        status=training_jobs.STATUS_SUCCEEDED,
    )

    assert written is None
    assert (await store.get("tenant-a", job["job_id"]))["status"] == training_jobs.STATUS_CANCELLED


@pytest.mark.asyncio
async def test_a_cancel_does_not_overwrite_a_finished_job():
    redis = FakeRedis()
    store = training_jobs.TrainingJobStore(redis)
    job, _ = await store.start("tenant-a", "user-1", "node")
    await store.update("tenant-a", job["job_id"], status=training_jobs.STATUS_RUNNING)
    real_get = store.get
    calls = {"n": 0}

    async def get_then_finish(tenant_id, job_id):
        # The cancel reads "running"; the worker finishes before it writes.
        current = await real_get(tenant_id, job_id)
        calls["n"] += 1
        if calls["n"] == 1:
            finished = {**current, "status": training_jobs.STATUS_SUCCEEDED, "result": {"ok": True}}
            await store._save(tenant_id, finished)
        return current

    store.get = get_then_finish
    returned = await store.cancel("tenant-a", job["job_id"])

    assert returned["status"] == training_jobs.STATUS_SUCCEEDED
    assert json.loads(redis.values[training_jobs.job_key("tenant-a", job["job_id"])])["result"] == {"ok": True}


@pytest.mark.asyncio
async def test_a_job_cancelled_before_it_starts_is_skipped(runner_env, monkeypatch):
    from app.modules.workflow.engine import workflow_engine

    engine = MagicMock()
    monkeypatch.setattr(workflow_engine, "WorkflowEngine", engine)
    job, _ = await runner_env.start("tenant-a", "user-1", "node")
    await runner_env.cancel("tenant-a", job["job_id"])

    await ml_training_job_tasks.run_training_job_async(job["job_id"], {"workflow_config": {}})

    engine.assert_not_called()
    assert (await runner_env.get("tenant-a", job["job_id"]))["status"] == training_jobs.STATUS_CANCELLED


@pytest.mark.asyncio
async def test_the_users_slot_outlives_the_longest_wait_plus_run():
    redis = FakeRedis()
    store = training_jobs.TrainingJobStore(redis)
    await store.start("tenant-a", "user-1", "node")

    ttl = redis.expiries["ml_training_job_active:tenant-a:user-1"]
    assert ttl >= training_jobs.QUEUED_TIMEOUT_SECONDS + training_jobs.JOB_TIMEOUT_SECONDS


@pytest.mark.asyncio
async def test_a_cancel_during_a_fit_does_not_restart_the_worker(runner_env, monkeypatch):
    from app.modules.workflow.engine import workflow_engine

    monkeypatch.setattr(training_jobs, "HEARTBEAT_SECONDS", 0.01)
    stop_worker = MagicMock()
    monkeypatch.setattr(ml_training_job_tasks, "_stop_worker", stop_worker)
    job, _ = await runner_env.start("tenant-a", "user-1", "node")
    release_fit = threading.Event()

    def fit():
        with training_progress.fitting():
            release_fit.wait(5)

    async def behaviour(_kwargs):
        await runner_env.cancel("tenant-a", job["job_id"])
        await asyncio.to_thread(fit)
        return _FakeState()

    monkeypatch.setattr(workflow_engine, "WorkflowEngine", _fake_engine(behaviour))
    try:
        await asyncio.wait_for(
            ml_training_job_tasks.run_training_job_async(job["job_id"], {"workflow_config": {}}), 2
        )
    finally:
        release_fit.set()

    assert (await runner_env.get("tenant-a", job["job_id"]))["status"] == training_jobs.STATUS_CANCELLED
    stop_worker.assert_not_called()


TRAINING_GRAPH_NODES = [
    {"id": "input", "type": "chatInputNode", "data": {}},
    {"id": "train", "type": "trainModelNode", "data": {"modelType": "knn"}},
    {"id": "form", "type": "humanInTheLoopNode", "data": {}},
    {"id": "output", "type": "chatOutputNode", "data": {}},
]
TRAINING_GRAPH_EDGES = [
    {"source": "input", "target": "train"},
    {"source": "train", "target": "form"},
    {"source": "form", "target": "output"},
]


def test_a_turn_from_the_start_reaches_the_train_model_node():
    found = training_jobs.train_model_nodes(TRAINING_GRAPH_NODES, TRAINING_GRAPH_EDGES, None)

    assert found == [{"modelType": "knn"}]


def test_resuming_after_the_training_step_runs_without_a_job():
    assert training_jobs.train_model_nodes(TRAINING_GRAPH_NODES, TRAINING_GRAPH_EDGES, "form") == []


def test_a_train_model_tool_attached_to_a_reachable_agent_counts():
    nodes = [
        {"id": "input", "type": "chatInputNode", "data": {}},
        {"id": "agent", "type": "agentNode", "data": {}},
        {"id": "train", "type": "trainModelNode", "data": {"modelType": "knn"}},
    ]
    edges = [
        {"source": "input", "target": "agent"},
        {"source": "train", "target": "agent", "targetHandle": "input_tools"},
    ]

    assert training_jobs.train_model_nodes(nodes, edges, "agent") == [{"modelType": "knn"}]


@pytest.mark.asyncio
async def test_a_hitl_resume_after_training_is_not_queued(route_env, monkeypatch):
    executed = {}

    async def fake_run_workflow_test(engine, owner_id, input_data, thread_id, start_node_id, usage_context):
        executed["start_node_id"] = start_node_id
        return {"status": "success"}

    monkeypatch.setattr(workflow_routes, "run_workflow_test", fake_run_workflow_test)
    monkeypatch.setattr(workflow_routes, "WorkflowEngine", MagicMock())
    workflow = {"id": "wf-1", "name": "t", "nodes": TRAINING_GRAPH_NODES, "edges": TRAINING_GRAPH_EDGES}

    response = await workflow_routes.test_workflow(
        NO_KEEPALIVE,
        {"input_data": {"thread_id": "t-1", "human_in_the_loop_node_id": "form"}, "workflow": workflow},
        workflow_id=None,
        workflow_service=MagicMock(),
    )

    assert response == {"status": "success"}
    assert executed["start_node_id"] == "form"
    route_env.delay.assert_not_called()


@pytest.mark.parametrize(
    "model_type, params, expected",
    [
        ("lightgbm", {"num_threads": -1}, {"n_jobs": 2}),
        ("lightgbm", {"num_threads": 1}, {"n_jobs": 1}),
        ("xgboost", {"nthread": 0, "max_depth": 3}, {"n_jobs": 2, "max_depth": 3}),
        ("xgboost", {"n_jobs": 1, "nthread": 16}, {"n_jobs": 1}),
    ],
)
def test_thread_aliases_are_capped_under_the_canonical_name(model_type, params, expected):
    assert model_registry.cap_estimator_threads(model_type, params, 2) == expected


def test_the_kept_model_gets_the_core_allowance_not_one_thread(monkeypatch):
    monkeypatch.setattr(settings, "ML_TRAINING_MAX_CORES", 2)
    rng = np.random.default_rng(0)
    X = pd.DataFrame({"a": rng.normal(size=40), "b": rng.normal(size=40)})

    result = hpo_module.optimize_hyperparameters(
        "random_forest",
        False,
        X,
        X["a"] * 2,
        "grid_search",
        {"n_estimators": 10, "max_depth": 3, "min_samples_split": 2, "max_features": "sqrt"},
        {"cvFolds": 2},
        is_time_based=False,
    )

    assert result["model"].get_params()["n_jobs"] == 2
    assert result["best_params"] == {
        key: value for key, value in result["model"].get_params().items() if key in result["best_params"]
    }
