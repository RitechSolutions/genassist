import pytest

import app.modules.workflow.utils as workflow_utils
from app.core.exceptions.exception_classes import AppException
from app.modules.workflow.engine.node_result import is_node_failure
from app.modules.workflow.engine.nodes import data_mapper_node
from app.modules.workflow.engine.nodes.data_mapper_node import DataMapperNode
from app.modules.workflow.engine.nodes.ml import ml_utils
from app.modules.workflow.engine.workflow_state import WorkflowState

RUNNER_ERROR = {"error": "Execution timed out after 600 seconds", "traceback": "", "output": "", "errors": ""}


async def _runner_error(*_args, **_kwargs):
    return dict(RUNNER_ERROR)


@pytest.mark.asyncio
async def test_data_mapper_runner_error_is_recorded_but_flows_unchanged(monkeypatch):
    monkeypatch.setattr(data_mapper_node, "execute_python_code", _runner_error)
    node_config = {"id": "m1", "type": "dataMapperNode", "data": {"name": "Mapper", "pythonScript": "result = 1"}}
    state = WorkflowState(
        workflow={"nodes": [node_config], "source_edges": {}, "target_edges": {}},
        initial_values={},
        thread_id="thread-1",
    )

    returned = await DataMapperNode("m1", node_config, state).execute()

    assert state.node_execution_status["m1"]["status"] == "failed"
    assert (
        state.node_execution_status["m1"]["error"] == "Data mapper script failed: Execution timed out after 600 seconds"
    )
    assert state.get_node_output("m1") == RUNNER_ERROR
    assert is_node_failure(returned) is not None


@pytest.mark.asyncio
async def test_preprocessing_runner_error_raises_when_raise_on_error(monkeypatch):
    monkeypatch.setattr(workflow_utils, "execute_python_code", _runner_error)

    with pytest.raises(AppException) as exc:
        await ml_utils.execute_and_process_preprocessing_code("result = df", None, None, "", raise_on_error=True)

    assert exc.value.error_detail == "Error executing preprocessing code: Execution timed out after 600 seconds"


@pytest.mark.asyncio
async def test_preprocessing_runner_error_returned_when_not_raising(monkeypatch):
    monkeypatch.setattr(workflow_utils, "execute_python_code", _runner_error)

    df, errors, response = await ml_utils.execute_and_process_preprocessing_code(
        "result = df", None, None, "", raise_on_error=False
    )

    assert df is None
    assert errors == "Execution timed out after 600 seconds"
    assert response == RUNNER_ERROR
