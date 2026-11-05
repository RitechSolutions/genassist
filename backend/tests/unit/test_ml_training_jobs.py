"""
Training runs as a background job with a core cap and a search-size limit.

Covers: counting a hyperparameter search's fits before it starts, refusing
one above ML_HPO_MAX_FITS, capping CV workers and estimator threads at
ML_TRAINING_MAX_CORES, the Redis job store, the /workflows test endpoints
queueing a job for Train Model, and the Celery job runner.
"""

import asyncio
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


class FakeRedis:
    def __init__(self):
        self.values = {}

    async def get(self, key):
        return self.values.get(key)

    async def set(self, key, value, ex=None):
        self.values[key] = value

    async def aclose(self):
        self.closed = True


class FakeSyncRedis:
    """The heartbeat thread's blocking client, writing into a FakeRedis's values."""

    def __init__(self, values):
        self.values = values

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
    job = await store.create("tenant-a", "user-1", "workflow")

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
        {"input_data": {"message": "go"}, "workflow": workflow}, workflow_id=None, workflow_service=MagicMock()
    )

    assert response.status_code == 202
    payload = route_env.delay.call_args.args[2]
    assert payload["input_data"] == {"message": "go"}
    assert payload["workflow_id"] == "wf-1"


@pytest.mark.asyncio
async def test_oversized_search_is_refused_before_queueing(route_env, monkeypatch):
    monkeypatch.setattr(settings, "ML_HPO_MAX_FITS", 100)

    with pytest.raises(AppException) as exc_info:
        await workflow_routes.test_individual_node(
            {"node_type": "trainModelNode", "node_config": TRAIN_NODE_CONFIG}
        )

    assert exc_info.value.error_key == ErrorKey.ML_TRAINING_SEARCH_TOO_LARGE
    route_env.delay.assert_not_called()
    assert route_env.redis.values == {}


@pytest.mark.asyncio
async def test_a_job_is_only_visible_to_the_user_who_started_it(route_env, monkeypatch):
    await workflow_routes.test_individual_node(
        {"node_type": "trainModelNode", "node_config": TRAIN_NODE_CONFIG}
    )
    job_id = route_env.delay.call_args.args[0]
    monkeypatch.setattr(workflow_routes, "get_current_user_id", lambda: "user-2")

    with pytest.raises(AppException) as exc_info:
        await workflow_routes.get_training_job(job_id)

    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_a_job_without_an_owner_is_not_visible_to_a_user(route_env, monkeypatch):
    monkeypatch.setattr(workflow_routes, "get_current_user_id", lambda: None)
    await workflow_routes.test_individual_node(
        {"node_type": "trainModelNode", "node_config": TRAIN_NODE_CONFIG}
    )
    job_id = route_env.delay.call_args.args[0]
    monkeypatch.setattr(workflow_routes, "get_current_user_id", lambda: "user-1")

    with pytest.raises(AppException) as exc_info:
        await workflow_routes.get_training_job(job_id)

    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_a_user_runs_one_training_job_at_a_time(route_env):
    request = {"node_type": "trainModelNode", "node_config": TRAIN_NODE_CONFIG}
    await workflow_routes.test_individual_node(request)
    first_job_id = route_env.delay.call_args.args[0]

    with pytest.raises(AppException) as exc_info:
        await workflow_routes.test_individual_node(request)

    assert exc_info.value.status_code == 409
    assert exc_info.value.error_key == ErrorKey.ML_TRAINING_JOB_ALREADY_RUNNING
    assert route_env.delay.call_count == 1

    # Once the first job has finished, the next test is queued.
    store = training_jobs.TrainingJobStore(route_env.redis)
    await store.update("tenant-a", first_job_id, status=training_jobs.STATUS_SUCCEEDED)
    response = await workflow_routes.test_individual_node(request)
    assert response.status_code == 202
    assert route_env.delay.call_count == 2


@pytest.mark.asyncio
async def test_a_failed_enqueue_marks_the_job_failed(route_env):
    route_env.delay.side_effect = ConnectionError("broker down")

    with pytest.raises(workflow_routes.HTTPException) as exc_info:
        await workflow_routes.test_individual_node(
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
    job = await runner_env.create("tenant-a", "user-1", "node")

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
    job = await runner_env.create("tenant-a", "user-1", "node")

    await ml_training_job_tasks.run_training_job_async(job["job_id"], {"workflow_config": {}})

    stored = await runner_env.get("tenant-a", job["job_id"])
    assert stored["status"] == training_jobs.STATUS_FAILED
    assert stored["error"] == "Search too large"
    assert stored["progress"]["stage"] == "training"


@pytest.mark.asyncio
async def test_runner_heartbeat_publishes_progress_while_training(runner_env, monkeypatch):
    from app.modules.workflow.engine import workflow_engine

    monkeypatch.setattr(training_jobs, "HEARTBEAT_SECONDS", 0.01)
    snapshots = []
    job = await runner_env.create("tenant-a", "user-1", "node")

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
    job = await runner_env.create("tenant-a", "user-1", "node")
    await runner_env.update("tenant-a", job["job_id"], status=training_jobs.STATUS_RUNNING)

    await ml_training_job_tasks.run_training_job_async(job["job_id"], {"workflow_config": {}})

    engine.assert_not_called()


@pytest.mark.asyncio
async def test_a_job_no_worker_started_in_time_is_failed_and_skipped(runner_env, monkeypatch):
    from app.modules.workflow.engine import workflow_engine

    job = await runner_env.create("tenant-a", "user-1", "node")
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
