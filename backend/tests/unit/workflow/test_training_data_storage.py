"""Training data written on one server can be read on any other, and after a restart."""

import re
import shutil
import uuid
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from starlette.requests import Request

from app.api.v1.routes import ml_models
from app.core.exceptions.error_messages import ErrorKey
from app.core.exceptions.exception_classes import AppException
from app.core.permissions.constants import Permissions as P
from app.core.tenant_scope import clear_tenant_context, set_tenant_context
from app.modules.filemanager.providers.local.provider import LocalFileSystemProvider
from app.modules.workflow.engine.nodes.ml import ml_utils, training_data_storage
from app.modules.workflow.engine.nodes.ml.train_data_source_node import TrainDataSourceNode
from app.modules.workflow.engine.nodes.ml.train_model_node import TrainModelNode
from app.modules.workflow.engine.nodes.ml.train_preprocess_node import TrainPreprocessNode
from app.modules.workflow.engine.workflow_state import WorkflowState
from tests.unit.ml_training_fixtures import removing_trained_models


class ObjectStorage:
    """An S3-like File Manager provider kept in memory."""

    name = "s3"

    def __init__(self):
        self.objects: dict[str, bytes] = {}
        self.downloads: list[str] = []
        self.upload_result = True

    def get_base_path(self) -> str:
        return "bucket"

    async def upload_file_from_local_path(self, local_path, key, file_metadata=None):
        if self.upload_result:
            self.objects[key] = Path(local_path).read_bytes()
        return self.upload_result

    async def file_exists(self, key):
        return key in self.objects

    async def download_file_to_path(self, key, local_path):
        self.downloads.append(key)
        Path(local_path).write_bytes(self.objects[key])
        return True


@pytest.fixture
def volume(tmp_path, monkeypatch):
    data_volume = tmp_path / "datavolume"
    (data_volume / "train").mkdir(parents=True)
    monkeypatch.setattr(ml_utils, "DATA_VOLUME", data_volume)
    monkeypatch.setattr(ml_utils, "extra_csv_directories", AsyncMock(return_value=[]))
    return data_volume


def _use_provider(monkeypatch, provider) -> AsyncMock:
    factory = AsyncMock(return_value=provider)
    monkeypatch.setattr(training_data_storage, "_storage_provider", factory)
    return factory


@pytest.fixture
def storage(monkeypatch):
    provider = ObjectStorage()
    _use_provider(monkeypatch, provider)
    return provider


@contextmanager
def tenant(slug: str):
    set_tenant_context(slug)
    try:
        yield
    finally:
        clear_tenant_context()


def _new_server(volume: Path) -> None:
    """Another server, or this one after a restart: nothing under DATA_VOLUME/train."""
    shutil.rmtree(volume / "train")
    (volume / "train").mkdir()


async def _write_output(thread_id: str = "thread-1") -> Path:
    path = await ml_utils.save_data_to_csv(
        [{"code": "001", "n": 1}, {"code": "002", "n": 2}],
        ["code", "n"],
        thread_id,
        suffix="_preprocess",
        dtypes={"code": "object", "n": "int64"},
    )
    return Path(path)


@pytest.mark.asyncio
async def test_output_is_stored_under_the_tenant_root(volume, storage):
    with tenant("acme"):
        csv_path = await _write_output()
        await training_data_storage.save_training_data(csv_path)

    folder = "tenants/acme/ml_training/thread-1"
    assert list(storage.objects) == [
        f"{folder}/{ml_utils.dtypes_sidecar_path(csv_path).name}",
        f"{folder}/{csv_path.name}",
    ]
    assert storage.objects[f"{folder}/{csv_path.name}"] == csv_path.read_bytes()


@pytest.mark.asyncio
async def test_another_server_downloads_the_output_with_its_column_types(volume, storage):
    with tenant("acme"):
        csv_path = await _write_output()
        await training_data_storage.save_training_data(csv_path)
        _new_server(volume)

        await training_data_storage.fetch_training_data(str(csv_path))
        loaded = ml_utils.load_csv_file(str(csv_path))

    # Column types arrive before the CSV, so a reader never sees the CSV without them
    assert [key.rsplit("/", 1)[1] for key in storage.downloads] == [
        ml_utils.dtypes_sidecar_path(csv_path).name,
        csv_path.name,
    ]
    assert loaded["code"].tolist() == ["001", "002"]
    assert not list(csv_path.parent.glob("*.part"))


@pytest.mark.asyncio
async def test_a_relative_reference_is_found_through_the_thread_folder(volume, storage):
    with tenant("acme"):
        csv_path = await _write_output()
        await training_data_storage.save_training_data(csv_path)
        _new_server(volume)

        await training_data_storage.fetch_training_data(csv_path.name, thread_id="thread-1")

    assert csv_path.exists()


@pytest.mark.asyncio
async def test_another_tenant_cannot_download_the_output(volume, storage):
    with tenant("acme"):
        csv_path = await _write_output()
        await training_data_storage.save_training_data(csv_path)
    _new_server(volume)

    with tenant("globex"):
        await training_data_storage.fetch_training_data(str(csv_path))
        with pytest.raises(AppException) as raised:
            ml_utils.load_csv_file(str(csv_path))

    assert raised.value.error_key == ErrorKey.FILE_NOT_FOUND
    assert storage.downloads == []


@pytest.mark.asyncio
async def test_a_file_that_is_here_is_read_without_storage(volume, monkeypatch):
    factory = _use_provider(monkeypatch, ObjectStorage())
    with tenant("acme"):
        csv_path = await _write_output()
        await training_data_storage.fetch_training_data(str(csv_path))

    factory.assert_not_awaited()


@pytest.mark.asyncio
async def test_a_file_path_resolution_finds_later_is_read_without_storage(volume, monkeypatch):
    # "uploads/data.csv" also points at DATA_VOLUME/train/uploads/data.csv, which isn't here
    factory = _use_provider(monkeypatch, ObjectStorage())
    local = volume / "uploads" / "data.csv"
    local.parent.mkdir()
    local.write_text("a\n1\n")
    with tenant("acme"):
        await training_data_storage.fetch_training_data("uploads/data.csv")

    factory.assert_not_awaited()


@pytest.mark.asyncio
async def test_only_csv_outputs_are_downloaded(volume, storage):
    storage.objects["tenants/acme/ml_training/thread-1/x.pkl"] = b"not training data"
    with tenant("acme"):
        await training_data_storage.fetch_training_data(f"{volume}/train/thread-1/x.pkl")

    assert storage.downloads == []
    assert not (volume / "train" / "thread-1" / "x.pkl").exists()


@pytest.mark.asyncio
async def test_train_data_source_reads_an_earlier_output_by_path_on_another_server(volume, storage):
    with tenant("acme"):
        csv_path = await _write_output()
        await training_data_storage.save_training_data(csv_path)
        _new_server(volume)
        node = TrainDataSourceNode("source", {"id": "source", "data": {}}, _running("source", "run-b"))
        result = await node.process(
            {"name": "Training Data", "sourceType": "csv", "csvFilePath": str(csv_path), "csvFileName": "data.csv"}
        )

    assert result["metadata"]["rowCount"] == 2


@pytest.mark.asyncio
@pytest.mark.parametrize("reference", ["train/../secret.csv", "uploads/data.csv"])
async def test_files_outside_the_training_folder_are_never_downloaded(volume, monkeypatch, reference):
    factory = _use_provider(monkeypatch, ObjectStorage())
    with tenant("acme"):
        await training_data_storage.fetch_training_data(f"{volume}/{reference}")

    factory.assert_not_awaited()


@pytest.mark.asyncio
async def test_files_outside_the_training_folder_are_never_stored(volume, monkeypatch, tmp_path):
    factory = _use_provider(monkeypatch, ObjectStorage())
    elsewhere = tmp_path / "elsewhere.csv"
    elsewhere.write_text("a\n1\n")
    with tenant("acme"):
        await training_data_storage.save_training_data(elsewhere)

    factory.assert_not_awaited()
    assert elsewhere.exists()


@pytest.mark.asyncio
async def test_default_local_provider_already_holds_the_output(volume, monkeypatch):
    _use_provider(monkeypatch, LocalFileSystemProvider({"base_path": str(volume)}))
    with tenant("acme"):
        csv_path = await _write_output()
        await training_data_storage.save_training_data(csv_path)
        stored = sorted(p.relative_to(volume) for p in volume.rglob("*") if p.is_file())
        _new_server(volume)
        await training_data_storage.fetch_training_data(str(csv_path))

    assert stored == sorted([csv_path.relative_to(volume), ml_utils.dtypes_sidecar_path(csv_path).relative_to(volume)])
    assert not csv_path.exists()


@pytest.mark.asyncio
async def test_local_provider_with_its_own_folder_keeps_a_copy(volume, monkeypatch, tmp_path):
    files = tmp_path / "files"
    _use_provider(monkeypatch, LocalFileSystemProvider({"base_path": str(files)}))
    with tenant("acme"):
        csv_path = await _write_output()
        await training_data_storage.save_training_data(csv_path)
        _new_server(volume)
        await training_data_storage.fetch_training_data(str(csv_path))
        loaded = ml_utils.load_csv_file(str(csv_path))

    assert (files / "tenants/acme/ml_training/thread-1" / csv_path.name).exists()
    assert loaded["code"].tolist() == ["001", "002"]


@pytest.mark.asyncio
async def test_a_failed_upload_keeps_the_output_on_this_server(volume, storage, caplog):
    storage.upload_result = False
    with tenant("acme"):
        csv_path = await _write_output()
        await training_data_storage.save_training_data(csv_path)

    assert csv_path.exists()
    assert ml_utils.dtypes_sidecar_path(csv_path).exists()
    assert "Could not save training data to file storage" in caplog.text


@pytest.mark.asyncio
async def test_train_data_source_still_succeeds_when_storage_fails(volume, storage):
    storage.upload_result = False
    source = volume / "uploads" / "source.csv"
    source.parent.mkdir()
    source.write_text("a,b\n1,2\n")
    node_config = {
        "id": "source",
        "type": "trainDataSourceNode",
        "data": {"sourceType": "csv", "csvFilePath": str(source), "csvFileName": "source.csv"},
    }
    state = WorkflowState(workflow={"nodes": [node_config], "source_edges": {}, "target_edges": {}}, thread_id="run-a")
    with tenant("acme"):
        await TrainDataSourceNode("source", node_config, state).execute()

    assert state.node_execution_status["source"]["status"] == "success"
    assert len(list((volume / "train").rglob("*.csv"))) == 1


@pytest.mark.asyncio
async def test_outputs_written_in_the_same_second_never_share_a_name(volume, monkeypatch):
    class FrozenClock:
        @staticmethod
        def now():
            return datetime(2026, 11, 5, 12, 0, 0)

    async def one_chunk():
        yield ["a"], [(1,)]

    monkeypatch.setattr(ml_utils, "datetime", FrozenClock)
    first = await _write_output()
    second = await _write_output()
    streamed, _, _, _ = await ml_utils.stream_rows_to_csv(one_chunk(), "thread-1", max_rows=10, max_bytes=1_000)

    assert len({first, second, Path(streamed)}) == 3
    # A random part, so another tenant can't work out a file's name from the time it was written
    assert re.fullmatch(r"thread-1_20261105_120000_[0-9a-f]{32}_preprocess\.csv", first.name)
    assert first.exists() and second.exists()


@pytest.mark.asyncio
async def test_a_file_in_the_working_folder_does_not_stop_the_download(volume, storage, tmp_path, monkeypatch):
    stored = volume / "train" / "thread-1" / "data.csv"
    stored.parent.mkdir()
    stored.write_text("a\n1\n")
    with tenant("acme"):
        await training_data_storage.save_training_data(stored)
        _new_server(volume)
        # Path resolution never reads this one: it's outside the data volume
        monkeypatch.chdir(tmp_path)
        (tmp_path / "data.csv").write_text("a\nunrelated\n")
        await training_data_storage.fetch_training_data("data.csv", thread_id="thread-1")

    assert stored.read_text() == "a\n1\n"


@pytest.mark.asyncio
async def test_a_storage_read_error_is_not_reported_as_file_not_found(volume, storage):
    storage.file_exists = AsyncMock(side_effect=RuntimeError("S3 unreachable"))
    with tenant("acme"):
        with pytest.raises(AppException) as raised:
            await training_data_storage.fetch_training_data(f"{volume}/train/thread-1/missing.csv")

    assert raised.value.error_key == ErrorKey.ML_TRAINING_DATA_STORAGE_FAILED
    assert raised.value.error_detail == training_data_storage.FETCH_FAILED_DETAIL


def _running(node_id: str, thread_id: str) -> WorkflowState:
    """A run's state, set up for one node the way the engine does before calling it."""
    state = WorkflowState(workflow={"nodes": [{"id": node_id, "data": {}}]}, thread_id=thread_id)
    state.start_node_execution(node_id)
    return state


def _analyze_request() -> Request:
    request = Request({"type": "http", "method": "POST", "path": "/", "headers": [], "query_string": b""})
    request.state.user = SimpleNamespace(permissions={P.MlModel.READ})
    return request


@pytest.mark.asyncio
async def test_each_step_works_on_a_server_that_did_not_run_the_one_before(volume, storage, monkeypatch):
    source = volume / "uploads" / "source.csv"
    source.parent.mkdir()
    source.write_text("code,count,target\n" + "".join(f"{i},{i % 7},{i * 1.5}\n" for i in range(40)))

    async def preprocess(python_code, df, file_url, raise_on_error=True):
        # Text with leading zeros only survives the trip if its column types travel with the CSV
        return df.assign(code=df["code"].map("{:03d}".format)), None, {}

    monkeypatch.setattr(ml_utils, "execute_and_process_preprocessing_code", preprocess)

    with tenant("acme"), removing_trained_models(monkeypatch):
        source_node = TrainDataSourceNode("source", {"id": "source", "data": {}}, _running("source", "run-a"))
        extracted = await source_node.process(
            {"name": "Training Data", "sourceType": "csv", "csvFilePath": str(source), "csvFileName": "source.csv"}
        )

        _new_server(volume)
        preprocess_node = TrainPreprocessNode("pre", {}, _running("pre", "run-b"))
        preprocessed = await preprocess_node.process({"pythonCode": "...", "fileUrl": extracted["data_path"]})
        assert preprocessed["success"] is True

        _new_server(volume)
        file_manager = MagicMock(extract_file_id_from_url=AsyncMock(return_value=None))
        analysis = await ml_models.analyze_csv(
            request=_analyze_request(),
            file_url=preprocessed["data_path"],
            file_id=None,
            file_name=None,
            python_code=None,
            file_manager_service=file_manager,
        )

        _new_server(volume)
        model_id = str(uuid.uuid4())
        model_node = TrainModelNode(model_id, {}, _running(model_id, "run-c"))
        trained = await model_node.process(
            {
                "name": f"storage-{uuid.uuid4().hex[:8]}",
                "modelType": "linear_regression",
                "fileUrl": preprocessed["data_path"],
                "targetColumn": "target",
                "featureColumns": ["count"],
                "validationSplit": 0.25,
            }
        )

    assert analysis["row_count"] == 40
    code = next(column for column in analysis["columns_info"] if column["name"] == "code")
    assert code["type"] == "categorical"
    assert code["categories"][:2] == ["000", "001"]
    assert trained["success"] is True
