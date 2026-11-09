"""Training node outputs name files inside the data volume, never by server path (TDS-24)."""

from pathlib import Path

import pytest

from app.modules.workflow.engine.nodes.ml import ml_utils


@pytest.fixture
def data_volume(monkeypatch, tmp_path):
    volume = tmp_path / "datavolume"
    (volume / "train").mkdir(parents=True)
    monkeypatch.setattr(ml_utils, "DATA_VOLUME", volume)
    return volume


def _write_csv(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("a,b\n1,2\n", encoding="utf-8")
    return path


def test_reference_is_relative_to_the_train_folder(data_volume):
    csv = _write_csv(data_volume / "train" / "thread-1" / "thread-1_20261107.csv")

    assert ml_utils.data_volume_reference(csv) == "thread-1/thread-1_20261107.csv"
    assert ml_utils.data_volume_reference(str(csv)) == "thread-1/thread-1_20261107.csv"


def test_model_reference_is_relative_to_the_data_volume(data_volume):
    pkl = data_volume / "ml_models" / "thread-1" / "model_v2.0.pkl"

    assert ml_utils.data_volume_reference(pkl, base="") == "ml_models/thread-1/model_v2.0.pkl"


def test_path_outside_the_folder_is_returned_unchanged(data_volume, tmp_path):
    outside = tmp_path / "elsewhere" / "file.csv"

    assert ml_utils.data_volume_reference(outside) == str(outside)


def test_lookalike_sibling_folder_is_not_treated_as_inside(data_volume):
    sibling = data_volume / "train-other" / "file.csv"

    assert ml_utils.data_volume_reference(sibling) == str(sibling)


def test_reference_resolves_in_the_same_thread(data_volume):
    csv = _write_csv(data_volume / "train" / "thread-1" / "thread-1_x.csv")

    resolved = ml_utils.resolve_csv_file_path("thread-1/thread-1_x.csv", thread_id="thread-1")

    assert resolved == Path(csv).resolve()


def test_reference_from_another_thread_resolves(data_volume):
    # Testing one node runs in a new thread but reads the upstream node's last output.
    csv = _write_csv(data_volume / "train" / "thread-1" / "thread-1_x.csv")

    resolved = ml_utils.resolve_csv_file_path("thread-1/thread-1_x.csv", thread_id="thread-2")

    assert resolved == Path(csv).resolve()


def test_reference_resolves_without_a_thread(data_volume):
    # The analyze/profile endpoints resolve the File URL with no thread.
    csv = _write_csv(data_volume / "train" / "thread-1" / "thread-1_x.csv")

    assert ml_utils.resolve_csv_file_path("thread-1/thread-1_x.csv") == Path(csv).resolve()


def test_absolute_path_from_an_older_run_still_resolves(data_volume):
    csv = _write_csv(data_volume / "train" / "thread-1" / "thread-1_x.csv")

    assert ml_utils.resolve_csv_file_path(str(csv), thread_id="thread-2") == Path(csv).resolve()


def test_reference_cannot_escape_the_data_volume(data_volume, tmp_path):
    _write_csv(tmp_path / "secret.csv")

    with pytest.raises(ml_utils.AppException):
        ml_utils.resolve_csv_file_path("../../secret.csv", thread_id="thread-1")


@pytest.mark.asyncio
async def test_registration_error_does_not_show_the_model_file_path(monkeypatch):
    from app.dependencies.injector import injector
    from app.modules.workflow.engine.nodes.ml.train_model_node import TrainModelNode
    from app.modules.workflow.engine.workflow_state import WorkflowState

    server_path = "/app/backend/datavolume/ml_models/thread-1/model_v2.0.pkl"

    def fail_upload(*_args, **_kwargs):
        raise FileNotFoundError(2, "No such file or directory", server_path)

    monkeypatch.setattr(injector, "get", fail_upload)
    node = TrainModelNode(node_id="train", node_config={}, state=WorkflowState(workflow={}))

    model_id, pkl_file_id, error, warnings = await node._register_trained_model(
        name="model",
        model_type="linear_regression",
        feature_columns=["x"],
        target_column="y",
        local_pkl_path=server_path,
    )

    assert (model_id, pkl_file_id, warnings) == (None, None, [])
    assert error == "Could not store the model file: No such file or directory"
    assert "/app/backend" not in error


def test_load_error_does_not_show_the_server_path(data_volume, monkeypatch):
    # An IO error from reading the file names the resolved server path.
    _write_csv(data_volume / "train" / "thread-1" / "thread-1_x.csv")

    def fail_read(path, *_args, **_kwargs):
        raise PermissionError(13, "Permission denied", str(path))

    monkeypatch.setattr(ml_utils, "read_csv_with_dtypes", fail_read)

    with pytest.raises(ml_utils.AppException) as raised:
        ml_utils.load_csv_file("thread-1/thread-1_x.csv", thread_id="thread-1")

    assert raised.value.error_detail == "Failed to load file: Permission denied"
    assert str(data_volume) not in raised.value.error_detail
