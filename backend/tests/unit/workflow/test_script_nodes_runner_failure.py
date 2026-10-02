import pandas as pd
import pytest

import app.modules.workflow.utils as workflow_utils
from app.core.exceptions.exception_classes import AppException
from app.modules.workflow.engine.node_result import is_node_failure
from app.modules.workflow.engine.nodes import data_mapper_node
from app.modules.workflow.engine.nodes.data_mapper_node import DataMapperNode
from app.modules.workflow.engine.nodes.ml import ml_utils
from app.modules.workflow.engine.workflow_state import WorkflowState

RUNNER_ERROR = {"error": "Execution timed out after 600 seconds", "traceback": "", "output": "", "errors": ""}
SCRIPT_ERROR = {
    "result": None,
    "output": "",
    "errors": "\nGlobal errors: Error processing parameters: KeyError: 'x'",
    "script_failed": True,
}
STDERR_ONLY = {
    "result": {"year": 2026},
    "output": "",
    "errors": "FutureWarning: Series.__getitem__ treating keys as positions",
}
NONE_WITH_WARNING = {"result": None, "output": "", "errors": "<string>:3: FutureWarning: fillna with 'method'"}
MAPPER = {"id": "m1", "type": "dataMapperNode", "data": {"name": "Mapper", "pythonScript": "result = 1"}}


async def _runner_error(*_args, **_kwargs):
    return dict(RUNNER_ERROR)


async def _run_data_mapper(monkeypatch, response):
    async def runner(*_args, **_kwargs):
        return dict(response)

    monkeypatch.setattr(data_mapper_node, "execute_python_code", runner)
    state = WorkflowState(
        workflow={"nodes": [MAPPER], "source_edges": {}, "target_edges": {}},
        initial_values={},
        thread_id="thread-1",
    )
    returned = await DataMapperNode("m1", MAPPER, state).execute()
    return state, returned


@pytest.mark.asyncio
async def test_data_mapper_runner_error_is_recorded_but_flows_unchanged(monkeypatch):
    state, returned = await _run_data_mapper(monkeypatch, RUNNER_ERROR)

    assert state.node_execution_status["m1"]["status"] == "failed"
    assert (
        state.node_execution_status["m1"]["error"] == "Data mapper script failed: Execution timed out after 600 seconds"
    )
    assert state.get_node_output("m1") == RUNNER_ERROR
    assert is_node_failure(returned) is not None


@pytest.mark.asyncio
async def test_data_mapper_script_exception_is_recorded(monkeypatch):
    state, returned = await _run_data_mapper(monkeypatch, SCRIPT_ERROR)

    assert state.node_execution_status["m1"]["status"] == "failed"
    assert "KeyError: 'x'" in state.node_execution_status["m1"]["error"]
    assert state.get_node_output("m1") == SCRIPT_ERROR
    assert is_node_failure(returned) is not None


@pytest.mark.asyncio
async def test_data_mapper_stderr_with_a_result_stays_success(monkeypatch):
    state, returned = await _run_data_mapper(monkeypatch, STDERR_ONLY)

    assert state.node_execution_status["m1"]["status"] == "success"
    assert returned == STDERR_ONLY


@pytest.mark.asyncio
async def test_data_mapper_none_result_with_a_warning_stays_success(monkeypatch):
    state, returned = await _run_data_mapper(monkeypatch, NONE_WITH_WARNING)

    assert state.node_execution_status["m1"]["status"] == "success"
    assert returned == NONE_WITH_WARNING


@pytest.mark.asyncio
async def test_preprocessing_sends_df_only_with_its_own_cap(monkeypatch):
    calls = []

    async def runner(code, params, wrap_code=True, **kwargs):
        calls.append((params, kwargs))
        return {"result": params["df"], "output": "", "errors": ""}

    monkeypatch.setattr(workflow_utils, "execute_python_code", runner)
    df = pd.DataFrame({"a": [1]})

    processed, errors, _ = await ml_utils.execute_and_process_preprocessing_code("", df, "")

    params, kwargs = calls[0]
    assert params["data"] is None and params["df"] is df
    assert kwargs["max_result_bytes"] == ml_utils._PREPROCESS_MAX_RESULT_BYTES
    assert errors is None and processed is df


@pytest.mark.asyncio
async def test_preprocessing_rebuilds_data_only_for_scripts_that_name_it(monkeypatch):
    preludes = []

    async def runner(code, params, wrap_code=True, **kwargs):
        preludes.append(kwargs["prelude"])
        return {"result": params["df"], "output": "", "errors": ""}

    monkeypatch.setattr(workflow_utils, "execute_python_code", runner)
    df = pd.DataFrame({"a": [1]})

    await ml_utils.execute_and_process_preprocessing_code("result = params['df']  # data", df, "")
    await ml_utils.execute_and_process_preprocessing_code("result = params.get('data')", df, "")

    assert preludes == ["", ml_utils._DATA_FROM_DF]


@pytest.mark.asyncio
async def test_preprocessing_rebuilds_data_from_df_in_the_sandbox():
    df = pd.DataFrame({"a": [1, 2], "b": [3.5, 4.5]})
    code = (
        "def executable_function(params):\n"
        "    assert params['data'] == params['df'].to_dict('records')\n"
        "    return params['df']\n"
    )

    processed, errors, _ = await ml_utils.execute_and_process_preprocessing_code(code, df, "", raise_on_error=False)

    assert errors is None
    pd.testing.assert_frame_equal(processed, df)


@pytest.mark.asyncio
async def test_preprocessing_runner_error_raises_when_raise_on_error(monkeypatch):
    monkeypatch.setattr(workflow_utils, "execute_python_code", _runner_error)

    with pytest.raises(AppException) as exc:
        await ml_utils.execute_and_process_preprocessing_code("result = df", None, "", raise_on_error=True)

    assert exc.value.error_detail == "Error executing preprocessing code: Execution timed out after 600 seconds"


@pytest.mark.asyncio
async def test_preprocessing_runner_error_returned_when_not_raising(monkeypatch):
    monkeypatch.setattr(workflow_utils, "execute_python_code", _runner_error)

    df, errors, response = await ml_utils.execute_and_process_preprocessing_code(
        "result = df", None, "", raise_on_error=False
    )

    assert df is None
    assert errors == "Execution timed out after 600 seconds"
    assert response == RUNNER_ERROR
