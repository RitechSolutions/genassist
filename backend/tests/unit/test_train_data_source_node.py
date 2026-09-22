from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.modules.workflow.engine.nodes.ml.train_data_source_node import (
    ExtractionLimits,
    TrainDataSourceNode,
)
from app.modules.workflow.engine.workflow_state import WorkflowState


@pytest.fixture
def node() -> TrainDataSourceNode:
    return TrainDataSourceNode(node_id="test", node_config={}, state=WorkflowState(workflow={}))


# Generously permissive - these tests are about csvFileId/csvFilePath priority,
# not about extraction limits, so nothing here should ever hit a real cap.
PERMISSIVE_LIMITS = ExtractionLimits(
    max_rows=1_000_000, max_bytes=1_000_000_000, query_timeout_seconds=30.0
)


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
        downloaded_path = tmp_path / "train" / "file-id-123.csv"

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
        ), patch(
            "app.modules.workflow.engine.nodes.ml.ml_utils.save_data_to_csv",
            new=AsyncMock(return_value=str(tmp_path / "saved.csv")),
        ):
            result = await node._process_csv_source(
                {
                    "csvFileId": "file-id-123",
                    # A path that does NOT exist anywhere on this machine -
                    # if the code used this directly, it would fail with
                    # file_not_found instead of succeeding via the download.
                    "csvFilePath": "/nonexistent/host/only/path.csv",
                },
                PERMISSIVE_LIMITS,
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

        with patch("app.dependencies.injector.injector.get") as mock_get, patch(
            "app.modules.workflow.engine.nodes.ml.ml_utils.save_data_to_csv",
            new=AsyncMock(return_value=str(tmp_path / "saved.csv")),
        ):
            result = await node._process_csv_source(
                {"csvFilePath": str(csv_path)}, PERMISSIVE_LIMITS
            )

        mock_get.assert_not_called()
        assert result["success"] is True
        assert result["metadata"]["columns"] == ["a", "b"]

    @pytest.mark.asyncio
    async def test_raises_when_neither_path_nor_id_given(self, node):
        from app.core.exceptions.exception_classes import AppException

        with pytest.raises(AppException):
            await node._process_csv_source({}, PERMISSIVE_LIMITS)
