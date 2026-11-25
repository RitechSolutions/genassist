"""
A pipeline run trains a new file for a registered model; it must not change
what the user set on that model. Its description stays as written, and its
type stays as registered. A run whose Train Model node trains another type is
refused instead of switching the type (for example, Random Forest to XGBoost).
"""

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.exceptions.error_messages import ErrorKey
from app.core.exceptions.exception_classes import AppException
from app.db.models.ml_model import ModelType as DbModelType
from app.db.models.ml_model_pipeline import PipelineRunStatus as PipelineRunStatusEnum
from app.dependencies.injector import injector
from app.modules.workflow.engine.nodes.ml.train_model_node import (
    ModelTypeMismatchError,
    TrainModelNode,
)
from app.modules.workflow.engine.workflow_state import WorkflowState
from app.schemas.ml_model_pipeline import MLModelPipelineRunPromote
from app.services.ml_model_pipeline import MLModelPipelineRunService
from app.services.ml_models import MODEL_TYPE_LABELS, model_type_mismatch_message
from app.services.workflow import WorkflowService


def _make_node(node_id=None, initial_values=None, config=None) -> TrainModelNode:
    state = WorkflowState(workflow={"config": config} if config else {})
    if initial_values is not None:
        state.initial_values = initial_values
    return TrainModelNode(node_id=node_id or str(uuid.uuid4()), node_config={}, state=state)


def _existing_model(model_type, description="Churn model for the EU stores"):
    existing = MagicMock()
    existing.id = uuid.uuid4()
    existing.name = "Churn"
    existing.description = description
    existing.model_type = model_type
    existing.inference_params = None
    existing.trained_by_workflow_id = None
    existing.trained_by_node_id = None
    return existing


class FakeWorkflows:
    def __init__(self):
        self.rows = {}

    def add(self, agent_id=None, nodes=(), is_deleted=False):
        workflow_id = uuid.uuid4()
        self.rows[workflow_id] = SimpleNamespace(agent_id=agent_id, nodes=list(nodes), is_deleted=is_deleted)
        return workflow_id

    async def get_agent_ids(self, workflow_ids):
        return {wid: self.rows[wid].agent_id for wid in workflow_ids if wid in self.rows}

    async def node_exists_outside(self, workflow_id, agent_id, node_id, node_name):
        return any(
            not row.is_deleted
            and wid != workflow_id
            and (agent_id is None or row.agent_id != agent_id)
            and any(n["id"] == node_id and n["data"]["name"] == node_name for n in row.nodes)
            for wid, row in self.rows.items()
        )


def _patch_dependencies(monkeypatch, ml_service, workflows=None):
    file_manager = MagicMock()
    provider = MagicMock()
    provider.get_base_path.return_value = "/data"
    provider.name = "local"
    file_manager.initialize = AsyncMock(return_value=provider)
    uploaded_file = MagicMock()
    uploaded_file.id = uuid.uuid4()
    file_manager.create_file_from_local_path = AsyncMock(return_value=uploaded_file)

    app_settings_service = MagicMock()
    app_settings_service.get_by_type_and_name = AsyncMock(return_value=MagicMock())

    from app.services.app_settings import AppSettingsService
    from app.services.file_manager import FileManagerService
    from app.services.ml_models import MLModelsService

    services = {
        FileManagerService: file_manager,
        AppSettingsService: app_settings_service,
        MLModelsService: ml_service,
        WorkflowService: WorkflowService(repository=workflows or FakeWorkflows()),
    }
    monkeypatch.setattr(injector, "get", lambda cls: services[cls])
    return file_manager


def _ml_service(existing=None, by_name=None):
    ml_service = MagicMock()
    ml_service.get_by_id = AsyncMock(return_value=existing)
    ml_service.get_by_name = AsyncMock(return_value=by_name)
    ml_service.update = AsyncMock(return_value=existing or by_name)
    created = MagicMock()
    created.id = uuid.uuid4()
    ml_service.create = AsyncMock(return_value=created)
    return ml_service


async def _register(node, model_type, target_model_id=None, name="Churn"):
    return await node._register_trained_model(
        name=name,
        model_type=model_type,
        feature_columns=["x"],
        target_column="y",
        local_pkl_path="/tmp/model.pkl",
        target_model_id=target_model_id,
    )


# -- model_type_mismatch_message ----------------------------------------------


def test_mismatch_message_names_both_types_with_ui_labels():
    message = model_type_mismatch_message("Churn", "random_forest", "xgboost")
    assert message is not None
    assert "'Churn' is registered as Random Forest" in message
    assert "set to XGBoost" in message
    assert "was not changed" in message


@pytest.mark.parametrize(
    "registered,trained",
    [
        ("random_forest", "random_forest"),
        (DbModelType.RANDOM_FOREST, "random_forest"),
        ("XGBoost", "xgboost"),
        (None, "xgboost"),
        ("xgboost", None),
    ],
)
def test_no_mismatch_for_same_type_or_missing_type(registered, trained):
    assert model_type_mismatch_message("Churn", registered, trained) is None


def test_every_model_type_has_a_label():
    assert set(MODEL_TYPE_LABELS) == {member.value for member in DbModelType}


def test_db_enum_is_compared_by_value():
    assert model_type_mismatch_message("Churn", DbModelType.RANDOM_FOREST, "xgboost")


# -- _register_trained_model --------------------------------------------------


@pytest.mark.asyncio
async def test_update_leaves_description_and_type_alone(monkeypatch):
    existing = _existing_model(DbModelType.RANDOM_FOREST)
    ml_service = _ml_service(existing=existing)
    _patch_dependencies(monkeypatch, ml_service)

    ml_model_id, pkl_file_id, error, warnings = await _register(
        _make_node(), "random_forest", target_model_id=str(existing.id)
    )

    assert error is None
    assert warnings == []
    assert ml_model_id == str(existing.id)
    assert pkl_file_id is not None
    update = ml_service.update.await_args.args[1]
    assert "description" not in update.model_fields_set
    assert "model_type" not in update.model_fields_set
    assert update.pkl_file_id == pkl_file_id


@pytest.mark.asyncio
async def test_create_sets_description_marker_and_type(monkeypatch):
    ml_service = _ml_service()
    _patch_dependencies(monkeypatch, ml_service)
    workflow_id = uuid.uuid4()
    node = _make_node(config={"id": str(workflow_id)})

    _, _, error, _ = await _register(node, "xgboost", name="Brand new")

    assert error is None
    create = ml_service.create.await_args.args[0]
    assert create.model_type.value == "xgboost"
    assert f"[train-model-node:{node.node_id}]" in create.description
    assert ml_service.create.await_args.kwargs["trained_by"] == (workflow_id, node.node_id)


@pytest.mark.asyncio
async def test_pipeline_target_of_another_type_fails_without_uploading(monkeypatch):
    existing = _existing_model(DbModelType.RANDOM_FOREST)
    ml_service = _ml_service(existing=existing)
    file_manager = _patch_dependencies(monkeypatch, ml_service)

    # Raised (not returned) so the node, and the pipeline run, fail.
    with pytest.raises(ModelTypeMismatchError) as excinfo:
        await _register(_make_node(), "xgboost", target_model_id=str(existing.id))

    assert "registered as Random Forest" in excinfo.value.error_detail
    # Checked before the upload, so no orphaned file is left behind.
    file_manager.create_file_from_local_path.assert_not_awaited()
    ml_service.update.assert_not_awaited()
    ml_service.create.assert_not_awaited()


@pytest.mark.asyncio
async def test_pipeline_target_lookup_failure_falls_back_and_keeps_the_file(monkeypatch):
    ml_service = _ml_service()
    ml_service.get_by_id = AsyncMock(side_effect=RuntimeError("db hiccup"))
    file_manager = _patch_dependencies(monkeypatch, ml_service)

    ml_model_id, pkl_file_id, error, _ = await _register(
        _make_node(), "xgboost", target_model_id=str(uuid.uuid4()), name="Brand new"
    )

    assert error is None
    assert ml_model_id is not None
    assert pkl_file_id == str(file_manager.create_file_from_local_path.return_value.id)


@pytest.mark.asyncio
async def test_registry_lookup_failure_uploads_nothing(monkeypatch):
    ml_service = _ml_service()
    ml_service.get_by_name = AsyncMock(side_effect=RuntimeError("db unavailable"))
    file_manager = _patch_dependencies(monkeypatch, ml_service)

    _, pkl_file_id, error, _ = await _register(_make_node(), "xgboost")

    assert error == "db unavailable"
    assert pkl_file_id is None
    file_manager.create_file_from_local_path.assert_not_awaited()


@pytest.mark.asyncio
async def test_a_name_another_node_holds_is_refused_before_the_upload(monkeypatch):
    """TM-19: the model is left alone and no file is uploaded."""
    other = _existing_model("xgboost", description=f"Trained by [train-model-node:{uuid.uuid4()}]")
    ml_service = _ml_service(by_name=other)
    file_manager = _patch_dependencies(monkeypatch, ml_service)

    node = _make_node(config={"id": str(uuid.uuid4())})

    with pytest.raises(AppException) as excinfo:
        await _register(node, "xgboost", name="Train Model")

    assert excinfo.value.error_key == ErrorKey.ML_MODEL_NAME_EXISTS
    assert excinfo.value.error_detail == (
        "A model named 'Train Model' already exists and was not trained by this node in this "
        "workflow, so it was left unchanged. Rename this node to train its own model."
    )
    file_manager.create_file_from_local_path.assert_not_awaited()
    ml_service.update.assert_not_awaited()
    ml_service.create.assert_not_awaited()


@pytest.mark.asyncio
async def test_a_failed_create_deletes_the_uploaded_file(monkeypatch):
    from app.core.exceptions.error_messages import ErrorKey
    from app.core.exceptions.exception_classes import AppException

    ml_service = _ml_service()
    # Another request registered the name between the lookup and the create.
    ml_service.create = AsyncMock(side_effect=AppException(error_key=ErrorKey.ML_MODEL_NAME_EXISTS))
    file_manager = _patch_dependencies(monkeypatch, ml_service)
    file_manager.delete_file = AsyncMock()

    ml_model_id, pkl_file_id, error, _ = await _register(_make_node(), "xgboost")

    assert ml_model_id is None and pkl_file_id is None and error
    file_manager.delete_file.assert_awaited_once_with(file_manager.create_file_from_local_path.return_value.id)


@pytest.mark.asyncio
async def test_a_pipeline_run_keeps_its_file_when_registering_fails(monkeypatch):
    # Promoting the run later attaches this file to the model.
    existing = _existing_model("xgboost")
    ml_service = _ml_service(existing=existing)
    ml_service.update = AsyncMock(side_effect=RuntimeError("db hiccup"))
    file_manager = _patch_dependencies(monkeypatch, ml_service)
    file_manager.delete_file = AsyncMock()

    _, pkl_file_id, error, _ = await _register(_make_node(), "xgboost", target_model_id=str(existing.id))

    assert error == "db hiccup"
    assert pkl_file_id == str(file_manager.create_file_from_local_path.return_value.id)
    file_manager.delete_file.assert_not_awaited()


@pytest.mark.asyncio
async def test_a_pipeline_run_whose_model_is_gone_still_uploads_its_file(monkeypatch):
    # The target model wasn't found and its name is another node's: the file
    # is still uploaded and kept, so the run can be promoted.
    other = _existing_model("xgboost", description=f"[train-model-node:{uuid.uuid4()}]")
    ml_service = _ml_service(by_name=other)
    ml_service.get_by_id = AsyncMock(side_effect=RuntimeError("not found"))
    ml_service.create = AsyncMock(side_effect=RuntimeError("A model with this name already exists."))
    file_manager = _patch_dependencies(monkeypatch, ml_service)
    file_manager.delete_file = AsyncMock()

    _, pkl_file_id, error, _ = await _register(_make_node(), "xgboost", target_model_id=str(uuid.uuid4()))

    assert error
    assert pkl_file_id == str(file_manager.create_file_from_local_path.return_value.id)
    file_manager.delete_file.assert_not_awaited()
    ml_service.update.assert_not_awaited()


@pytest.mark.asyncio
async def test_failed_cleanup_still_reports_the_registration_error(monkeypatch):
    ml_service = _ml_service()
    ml_service.create = AsyncMock(side_effect=RuntimeError("registry unavailable"))
    file_manager = _patch_dependencies(monkeypatch, ml_service)
    file_manager.delete_file = AsyncMock(side_effect=RuntimeError("storage down"))

    _, pkl_file_id, error, _ = await _register(_make_node(), "xgboost")

    assert error == "registry unavailable"
    assert pkl_file_id is None


@pytest.mark.asyncio
async def test_node_own_ad_hoc_model_follows_the_node_type_but_keeps_description(monkeypatch):
    workflow_id = uuid.uuid4()
    node = _make_node(config={"id": str(workflow_id)})
    description = f"My notes [train-model-node:{node.node_id}]"
    own = _existing_model("linear_regression", description=description)
    ml_service = _ml_service(by_name=own)
    _patch_dependencies(monkeypatch, ml_service)

    ml_model_id, _, error, _ = await _register(node, "ridge_regression", name="Train Model")

    assert error is None
    assert ml_model_id == str(own.id)
    update = ml_service.update.await_args.args[1]
    assert update.model_type.value == "ridge_regression"
    assert "description" not in update.model_fields_set
    assert ml_service.update.await_args.kwargs["trained_by"] == (workflow_id, node.node_id)


# -- process(): fail before training ------------------------------------------


@pytest.mark.asyncio
async def test_target_type_check_without_pipeline_target_is_skipped():
    assert await _make_node()._target_model_type_mismatch(None, "xgboost") is None


@pytest.mark.asyncio
async def test_target_type_check_ignores_lookup_failures(monkeypatch):
    ml_service = MagicMock()
    ml_service.get_by_id = AsyncMock(side_effect=AppException(error_key=ErrorKey.NOT_FOUND))
    _patch_dependencies(monkeypatch, ml_service)
    assert await _make_node()._target_model_type_mismatch(str(uuid.uuid4()), "xgboost") is None

    ml_service.get_by_id = AsyncMock(return_value=None)
    assert await _make_node()._target_model_type_mismatch(str(uuid.uuid4()), "xgboost") is None


@pytest.mark.asyncio
async def test_pipeline_run_fails_before_training_on_type_mismatch(monkeypatch, tmp_path):
    existing = _existing_model(DbModelType.RANDOM_FOREST)
    ml_service = _ml_service(existing=existing)
    _patch_dependencies(monkeypatch, ml_service)
    node = _make_node(initial_values={"model_id": str(existing.id)})
    node._register_trained_model = AsyncMock()

    with pytest.raises(AppException) as excinfo:
        await node.process(
            {
                "name": "Train Model",
                "modelType": "xgboost",
                # Never read: the run stops before loading data.
                "fileUrl": str(tmp_path / "missing.csv"),
                "targetColumn": "y",
                "featureColumns": ["x"],
            }
        )

    assert "registered as Random Forest" in excinfo.value.error_detail
    assert "set to XGBoost" in excinfo.value.error_detail
    node._register_trained_model.assert_not_awaited()


NODE = "5f0c1a52-7d0e-4b7e-9a55-0c8c3f6d2b11"
TRAIN_NODE = {"id": NODE, "type": "trainModelNode", "data": {"name": "Churn"}}
TAKEN = (
    "A model named 'Churn' already exists and was not trained by this node in this "
    "workflow, so it was left unchanged. Rename this node to train its own model."
)
COPIED = (
    "Another workflow has a copy of this node with the same name, so the model 'Churn' "
    "was left unchanged. Rename this node, or the node in the copy, to train separate models."
)


class FakeRegistry:
    def __init__(self):
        self.rows = {}
        self.clock = 0

    def add(self, description, target_variable="y"):
        row = SimpleNamespace(
            id=uuid.uuid4(), name="Churn", description=description, model_type="xgboost",
            inference_params=None, target_variable=target_variable, pkl_file_id="old", updated_at=0,
            trained_by_workflow_id=None, trained_by_node_id=None,
        )
        self.rows[row.id] = row
        return row

    async def get_by_name(self, name):
        return next((row for row in self.rows.values() if row.name == name), None)

    async def get_by_id(self, model_id):
        return self.rows.get(model_id)

    def _stamp(self, row, trained_by):
        self.clock += 1
        row.updated_at = self.clock
        if trained_by is not None:
            row.trained_by_workflow_id, row.trained_by_node_id = trained_by

    async def create(self, data, trained_by=None, **_):
        if await self.get_by_name(data.name):
            raise AppException(error_key=ErrorKey.ML_MODEL_NAME_EXISTS)
        row = SimpleNamespace(
            **data.model_dump(), id=uuid.uuid4(), trained_by_workflow_id=None, trained_by_node_id=None
        )
        self._stamp(row, trained_by)
        self.rows[row.id] = row
        return row

    async def update(self, model_id, data, trained_by=None, **_):
        row = self.rows[model_id]
        for key, value in data.model_dump(exclude_unset=True).items():
            setattr(row, key, value)
        self._stamp(row, trained_by)
        return row


@pytest.fixture
def owners(monkeypatch):
    registry, workflows = FakeRegistry(), FakeWorkflows()
    files = _patch_dependencies(monkeypatch, registry, workflows)
    files.create_file_from_local_path = AsyncMock(side_effect=lambda *a, **k: SimpleNamespace(id=uuid.uuid4()))
    files.delete_file = AsyncMock()
    return SimpleNamespace(registry=registry, workflows=workflows, files=files)


def _run(config, node_id=NODE, initial_values=None):
    return _make_node(node_id=node_id, initial_values=initial_values, config=config)


async def _train(node, name="Churn", **kwargs):
    return await node._register_trained_model(
        name=name, model_type="xgboost", feature_columns=["x"], target_column="y",
        local_pkl_path="/tmp/model.pkl", **kwargs,
    )


async def _refused(node, name="Churn") -> str:
    with pytest.raises(AppException) as excinfo:
        await _train(node, name=name)
    assert excinfo.value.error_key == ErrorKey.ML_MODEL_NAME_EXISTS
    return excinfo.value.error_detail


def _copy_config(via, workflow_id):
    return {
        "workflow run": {"id": str(workflow_id)},
        "Test Node": {"id": "test-trainModelNode-1731600000", "saved_workflow_id": str(workflow_id)},
        "Test Workflow": {"id": "test-workflow", "saved_workflow_id": str(workflow_id)},
    }[via]


@pytest.mark.asyncio
@pytest.mark.parametrize("via", ["workflow run", "Test Node", "Test Workflow"])
async def test_a_copy_is_refused_and_the_original_is_untouched(owners, via):
    original = owners.workflows.add(agent_id=uuid.uuid4(), nodes=[TRAIN_NODE])
    copy = owners.workflows.add(agent_id=uuid.uuid4(), nodes=[TRAIN_NODE])
    model_id, pkl_file_id, _, _ = await _train(_run({"id": str(original)}))
    row = owners.registry.rows[uuid.UUID(model_id)]
    uploads = owners.files.create_file_from_local_path.await_count

    assert await _refused(_run(_copy_config(via, copy))) == TAKEN

    assert (row.pkl_file_id, row.updated_at) == (pkl_file_id, 1)
    assert owners.files.create_file_from_local_path.await_count == uploads


@pytest.mark.asyncio
async def test_a_renamed_copy_trains_its_own_model_and_the_original_retrains_its_own(owners):
    original = owners.workflows.add(agent_id=uuid.uuid4(), nodes=[TRAIN_NODE])
    copy = owners.workflows.add(agent_id=uuid.uuid4(), nodes=[TRAIN_NODE])
    original_id, *_ = await _train(_run({"id": str(original)}))

    copy_id, _, error, _ = await _train(_run({"id": str(copy)}), name="Churn copy")
    again_id, again_file, _, _ = await _train(_run({"id": str(original)}))

    assert error is None and copy_id != original_id
    copy_row = owners.registry.rows[uuid.UUID(copy_id)]
    assert (copy_row.trained_by_workflow_id, copy_row.trained_by_node_id) == (copy, NODE)
    original_row = owners.registry.rows[uuid.UUID(original_id)]
    assert again_id == original_id
    assert (original_row.pkl_file_id, original_row.updated_at) == (again_file, 3)
    assert copy_row.updated_at == 2


@pytest.mark.asyncio
async def test_a_new_version_keeps_the_model_after_the_first_version_is_deleted(owners):
    agent_id = uuid.uuid4()
    v1 = owners.workflows.add(agent_id=agent_id)
    v2 = owners.workflows.add(agent_id=agent_id)
    model_id, *_ = await _train(_run({"id": str(v1)}))
    owners.workflows.rows[v1].is_deleted = True

    again_id, _, error, _ = await _train(_run({"id": str(v2)}))

    assert (again_id, error) == (model_id, None)
    assert owners.registry.rows[uuid.UUID(model_id)].trained_by_workflow_id == v2


@pytest.mark.asyncio
async def test_a_workflow_without_an_agent_keeps_its_model_and_another_one_is_refused(owners):
    workflow = owners.workflows.add()
    other = owners.workflows.add()
    model_id, *_ = await _train(_run({"id": str(workflow)}))
    owners.workflows.rows[workflow].agent_id = uuid.uuid4()

    again_id, _, error, _ = await _train(_run({"id": str(workflow)}))

    assert (again_id, error) == (model_id, None)
    assert await _refused(_run({"id": str(other)})) == TAKEN


@pytest.mark.asyncio
async def test_a_model_from_before_the_fix_is_kept_from_both_while_a_saved_copy_has_the_name(owners):
    row = owners.registry.add(f"notes [train-model-node:{NODE}]")
    original = owners.workflows.add(agent_id=uuid.uuid4(), nodes=[TRAIN_NODE])
    copy = owners.workflows.add(agent_id=uuid.uuid4(), nodes=[TRAIN_NODE])

    assert await _refused(_run({"id": str(original)})) == COPIED
    assert await _refused(_run({"id": str(copy)})) == COPIED
    assert row.pkl_file_id == "old"

    owners.workflows.rows[copy].nodes = [{**TRAIN_NODE, "data": {"name": "Churn copy"}}]
    model_id, _, error, _ = await _train(_run({"id": str(original)}))

    assert (model_id, error) == (str(row.id), None)
    assert (row.trained_by_workflow_id, row.trained_by_node_id) == (original, NODE)
    assert row.description == f"notes [train-model-node:{NODE}]"


@pytest.mark.asyncio
async def test_a_deleted_copy_does_not_block_adopting_a_model_from_before_the_fix(owners):
    row = owners.registry.add(f"[train-model-node:{NODE}]")
    original = owners.workflows.add(agent_id=uuid.uuid4(), nodes=[TRAIN_NODE])
    owners.workflows.add(agent_id=uuid.uuid4(), nodes=[TRAIN_NODE], is_deleted=True)

    model_id, _, error, _ = await _train(_run({"id": str(original)}))

    assert (model_id, error) == (str(row.id), None)


@pytest.mark.asyncio
async def test_an_unknown_workflow_creates_a_model_without_an_owner_and_never_updates_it(owners):
    node = _run({"id": "test-trainModelNode-1731600000"})

    model_id, _, error, _ = await _train(node)
    row = owners.registry.rows[uuid.UUID(model_id)]

    assert error is None
    assert (row.trained_by_workflow_id, row.trained_by_node_id) == (None, None)
    assert f"[train-model-node:{NODE}]" in row.description
    assert await _refused(node) == TAKEN


@pytest.mark.asyncio
async def test_an_old_test_model_is_taken_over_only_by_a_test_node_that_names_its_workflow(owners):
    row = owners.registry.add("Trained (thread t) [train-model-node:test-trainModelNode-1731000000]")
    workflow = owners.workflows.add(agent_id=uuid.uuid4())

    assert await _refused(_run({"id": "test-trainModelNode-1731600000"})) == TAKEN
    assert await _refused(_run({"id": str(workflow)})) == TAKEN
    model_id, *_ = await _train(
        _run({"id": "test-trainModelNode-1731600000", "saved_workflow_id": str(workflow)})
    )

    assert model_id == str(row.id)
    assert (row.trained_by_workflow_id, row.trained_by_node_id) == (workflow, NODE)


@pytest.mark.asyncio
async def test_a_model_registered_by_hand_is_refused(owners):
    owners.registry.add("Registered by hand")

    assert await _refused(_run({"id": str(owners.workflows.add())})) == TAKEN


@pytest.mark.asyncio
async def test_a_pipeline_run_updates_its_model_by_id_and_leaves_the_owner(owners):
    original = owners.workflows.add(agent_id=uuid.uuid4())
    model_id, *_ = await _train(_run({"id": str(original)}))
    row = owners.registry.rows[uuid.UUID(model_id)]

    pipeline_node = _run({"id": str(owners.workflows.add())}, node_id="pipeline-node")
    got, _, error, _ = await _train(pipeline_node, name="Train Model", target_model_id=model_id)

    assert (got, error) == (model_id, None)
    assert row.updated_at == 2
    assert (row.trained_by_workflow_id, row.trained_by_node_id) == (original, NODE)


@pytest.mark.asyncio
async def test_a_create_race_is_still_a_registration_error_without_the_file(owners):
    owners.registry.create = AsyncMock(side_effect=AppException(error_key=ErrorKey.ML_MODEL_NAME_EXISTS))

    model_id, pkl_file_id, error, _ = await _train(_run({"id": str(owners.workflows.add())}))

    assert (model_id, pkl_file_id) == (None, None) and error
    owners.files.delete_file.assert_awaited_once()


@pytest.mark.asyncio
async def test_a_copy_fails_before_training(owners, tmp_path):
    original = owners.workflows.add(agent_id=uuid.uuid4(), nodes=[TRAIN_NODE])
    await _train(_run({"id": str(original)}))
    node = _run({"id": str(owners.workflows.add(agent_id=uuid.uuid4(), nodes=[TRAIN_NODE]))})
    node._register_trained_model = AsyncMock()

    with pytest.raises(AppException) as excinfo:
        await node.process(
            {
                "name": "Churn",
                "modelType": "xgboost",
                # Never read: the run stops before loading data.
                "fileUrl": str(tmp_path / "missing.csv"),
                "targetColumn": "y",
                "featureColumns": ["x"],
            }
        )

    assert excinfo.value.error_detail == TAKEN
    node._register_trained_model.assert_not_awaited()


@pytest.mark.asyncio
async def test_a_failed_name_check_before_training_lets_the_run_go_on(owners):
    owners.registry.get_by_name = AsyncMock(side_effect=RuntimeError("db unavailable"))

    assert await _run({"id": str(uuid.uuid4())})._name_refusal("Churn", "y") is None


# -- promote_run --------------------------------------------------------------


def _promote_service(model_type, run_model_type):
    model_id = uuid.uuid4()
    run = MagicMock()
    run.model_id = model_id
    run.status = PipelineRunStatusEnum.COMPLETED
    run.execution_output = {
        "output": {
            "model_type": run_model_type,
            "model_file_path": "/data/model.pkl",
            "pkl_file_id": str(uuid.uuid4()),
            "feature_columns": ["x"],
            "target_column": "y",
        }
    }
    run_repository = MagicMock()
    run_repository.get_by_id = AsyncMock(return_value=run)

    config = MagicMock()
    config_repository = MagicMock()
    config_repository.get_by_id = AsyncMock(return_value=config)
    config_repository.unset_default_for_model = AsyncMock()
    config_repository.update = AsyncMock(return_value=config)

    model = MagicMock()
    model.name = "Churn"
    model.model_type = model_type
    model.inference_params = None
    model_repository = MagicMock()
    model_repository.get_by_id = AsyncMock(return_value=model)

    model_service = MagicMock()
    model_service.update = AsyncMock(return_value=model)

    service = MLModelPipelineRunService(
        run_repository=run_repository,
        config_repository=config_repository,
        model_repository=model_repository,
        model_service=model_service,
        model_manager=MagicMock(),
        workflow_repository=MagicMock(),
    )
    return service, model_service, config_repository, model_id


@pytest.mark.asyncio
async def test_promote_refuses_a_file_of_another_type():
    service, model_service, config_repository, model_id = _promote_service(
        DbModelType.RANDOM_FOREST, "xgboost"
    )

    with pytest.raises(AppException) as excinfo:
        await service.promote_run(
            model_id, uuid.uuid4(), MLModelPipelineRunPromote(update_model_file=True)
        )

    assert excinfo.value.error_key == ErrorKey.ML_PIPELINE_RUN_NOT_PROMOTABLE
    assert "registered as Random Forest" in excinfo.value.error_detail
    model_service.update.assert_not_awaited()
    config_repository.unset_default_for_model.assert_not_awaited()


@pytest.mark.asyncio
async def test_promote_accepts_a_file_of_the_same_type():
    service, model_service, _, model_id = _promote_service(
        DbModelType.RANDOM_FOREST, "random_forest"
    )

    await service.promote_run(
        model_id, uuid.uuid4(), MLModelPipelineRunPromote(update_model_file=True)
    )

    update = model_service.update.await_args.args[1]
    assert "model_type" not in update.model_fields_set
    assert "description" not in update.model_fields_set
