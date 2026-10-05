from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.exceptions.error_messages import ErrorKey
from app.core.exceptions.exception_classes import AppException
from app.modules.workflow.engine.nodes.ml.train_data_source_node import TrainDataSourceNode
from app.modules.workflow.engine.workflow_state import WorkflowState
from app.schemas.dynamic_form_schemas.nodes.train_data_source_schema import (
    TRAIN_DATA_SOURCE_NODE_DIALOG_SCHEMA,
)


@pytest.fixture
def node() -> TrainDataSourceNode:
    return TrainDataSourceNode(node_id="test", node_config={}, state=WorkflowState(workflow={}))


class TestProcessCsvSourcePrefersDownloadById:
    @pytest.mark.asyncio
    async def test_downloads_by_id_even_when_csv_file_path_is_also_given(self, node, tmp_path):
        """
        A stored csvFilePath is an absolute path captured wherever the file
        was originally uploaded from - it can be unresolvable in whatever
        process actually executes this node (e.g. a scheduled pipeline run
        in a different container). When a csvFileId is available, it must
        always be used to re-download the file fresh, ignoring csvFilePath,
        instead of trusting a path that may not exist here.
        """
        async def fake_download(file_id, path):
            from pathlib import Path

            Path(path).parent.mkdir(parents=True, exist_ok=True)
            Path(path).write_text("col1,col2\n1,2\n")

        mock_file_manager = MagicMock()
        mock_file_manager.download_file_to_path = AsyncMock(side_effect=fake_download)

        with patch(
            "app.modules.workflow.engine.nodes.ml.train_data_source_node.DATA_VOLUME",
            tmp_path,
        ), patch(
            "app.dependencies.injector.injector.get", return_value=mock_file_manager
        ):
            result = await node._process_csv_source(
                {
                    "csvFileId": "file-id-123",
                    # A path that does NOT exist anywhere on this machine -
                    # if the code used this directly, it would fail with
                    # file_not_found instead of succeeding via the download.
                    "csvFilePath": "/nonexistent/host/only/path.csv",
                },
                node._resolve_extraction_limits({}),
                1,
            )

        mock_file_manager.download_file_to_path.assert_called_once()
        call_args = mock_file_manager.download_file_to_path.call_args
        assert call_args.args[0] == "file-id-123"
        assert result["success"] is True
        assert result["metadata"]["columns"] == ["col1", "col2"]

    @pytest.mark.asyncio
    async def test_falls_back_to_csv_file_path_when_no_id(self, node, tmp_path):
        csv_path = tmp_path / "uploaded.csv"
        csv_path.write_text("a,b\n1,2\n")

        with patch("app.dependencies.injector.injector.get") as mock_get:
            result = await node._process_csv_source(
                {"csvFilePath": str(csv_path)},
                node._resolve_extraction_limits({}),
                1,
            )

        mock_get.assert_not_called()
        assert result["success"] is True
        assert result["metadata"]["columns"] == ["a", "b"]

    @pytest.mark.asyncio
    async def test_raises_when_neither_path_nor_id_given(self, node):
        with pytest.raises(AppException):
            await node._process_csv_source(
                {},
                node._resolve_extraction_limits({}),
                1,
            )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "config",
    [
        {},
        {"sourceType": None},
        {"sourceType": ""},
        {"sourceType": "file"},
        {"sourceType": 1},
        {"sourceType": ["csv"]},
    ],
)
async def test_process_rejects_missing_or_unsupported_source_types(node, config):
    with pytest.raises(AppException) as exc_info:
        await node.process(config)

    assert exc_info.value.error_key == ErrorKey.ML_EXTRACT_CONFIGURATION_INVALID
    assert exc_info.value.error_detail == (
        "Choose a database or uploaded file for Train Data Source."
    )


@pytest.mark.asyncio
async def test_saved_workflow_legacy_fields_do_not_change_file_execution(
    node, tmp_path
):
    source = tmp_path / "saved-workflow.csv"
    source.write_text("id,name\n1,Ada\n", encoding="utf-8")
    config = {
        "sourceType": "csv",
        "csvFilePath": str(source),
        # Existing workflow data can still contain fields retired from the
        # backend dialog schema. They must remain harmless extra data.
        "dataSourceType": "database",
        "csvFile": "legacy-placeholder",
    }

    with patch(
        "app.modules.workflow.engine.nodes.ml.ml_utils.DATA_VOLUME",
        tmp_path,
    ):
        result = await node.process(config)

    assert result["success"] is True
    assert result["data"] == [{"id": "1", "name": "Ada"}]
    assert result["metadata"] == {"rowCount": 1, "columns": ["id", "name"]}


def test_dialog_schema_lists_source_fields():
    fields = {field.name: field for field in TRAIN_DATA_SOURCE_NODE_DIALOG_SCHEMA}

    assert list(fields) == [
        "name",
        "sourceType",
        "dataSourceId",
        "query",
        "csvFileName",
        "csvFilePath",
        "csvFileId",
        "csvFileUrl",
    ]
    assert fields["sourceType"].options == [
        {"label": "Database", "value": "datasource"},
        {"label": "Uploaded File", "value": "csv"},
    ]
    assert fields["dataSourceId"].conditional.model_dump() == {
        "field": "sourceType",
        "value": "datasource",
    }
    assert fields["csvFileId"].conditional.model_dump() == {
        "field": "sourceType",
        "value": "csv",
    }
