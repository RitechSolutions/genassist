"""
DP-19: a Data Preprocessing node with no input file fails with a message
naming the problem (no source, more than one, or a source that has not run),
instead of reading "File not found: null" or reporting success.
"""

import pandas as pd
import pytest

import app.modules.workflow.utils as workflow_utils
from app.modules.workflow.engine.node_result import is_node_failure
from app.modules.workflow.engine.nodes.ml.train_preprocess_node import TrainPreprocessNode
from app.modules.workflow.engine.workflow_state import WorkflowState

CODE = "def executable_function(params):\n    return params['df']\n"


def _node(sources, other_edges=()):
    nodes = [{"id": "prep", "type": "preprocessingNode", "data": {"name": "Preprocess"}}]
    nodes += [{"id": s, "type": "trainDataSourceNode", "data": {"name": f"Source {s}"}} for s in sources]
    edges = [{"source": s, "target": "prep", "targetHandle": "input"} for s in sources]
    edges += list(other_edges)
    state = WorkflowState(workflow={"nodes": nodes, "edges": edges, "target_edges": {"prep": edges}})
    state.node_execution_status["prep"] = {}
    return TrainPreprocessNode(node_id="prep", node_config=nodes[0], state=state)


@pytest.mark.asyncio
@pytest.mark.parametrize("file_url", ["null", "None", "{{source.data_path}}"])
async def test_no_source_connected(file_url):
    # The workflow has other wiring, just none into this node
    result = await _node([], [{"source": "x", "target": "y"}]).process({"pythonCode": CODE, "fileUrl": file_url})
    failure = is_node_failure(result)
    assert failure is not None
    assert failure["error"].startswith("No data source is connected to this node.")
    assert "null" not in failure["error"]


@pytest.mark.asyncio
async def test_node_tested_on_its_own_asks_for_the_path():
    """Test Node runs the node alone, with no edges at all."""
    result = await _node([]).process({"pythonCode": CODE, "fileUrl": "null"})
    assert is_node_failure(result)["error"].startswith("No input file: enter the data file path")


@pytest.mark.asyncio
async def test_more_than_one_source_connected():
    result = await _node(["a", "b"]).process({"pythonCode": CODE, "fileUrl": "null"})
    error = is_node_failure(result)["error"]
    assert error.startswith("2 nodes are connected to this node's input (Source a, Source b).")


@pytest.mark.asyncio
async def test_source_without_a_file_yet():
    result = await _node(["a"]).process({"pythonCode": CODE, "fileUrl": "null"})
    assert is_node_failure(result)["error"].startswith("Source a has no data file for this node yet.")


@pytest.mark.asyncio
async def test_failed_code_fails_the_node_with_the_short_message(monkeypatch):
    from app.modules.workflow.engine.nodes.ml import ml_utils

    monkeypatch.setattr(ml_utils, "load_csv_file", lambda *a, **k: pd.DataFrame({"city": ["x"]}))

    async def no_extra_dirs():
        return []

    monkeypatch.setattr(ml_utils, "extra_csv_directories", no_extra_dirs)

    async def runner(*_args, **_kwargs):
        return {
            "result": None,
            "output": "",
            "errors": "",
            "script_error": (
                "Error processing parameters: 'citty'\nTraceback (most recent call last):\n"
                '  File "/opt/venv/lib/python3.12/site-packages/pandas/core/frame.py", line 1\n'
                "KeyError: 'citty'\n"
            ),
        }

    monkeypatch.setattr(workflow_utils, "execute_python_code", runner)
    result = await _node(["a"]).process({"pythonCode": CODE, "fileUrl": "data.csv"})
    failure = is_node_failure(result)
    assert failure["error"] == "KeyError: 'citty'"
    assert failure["output"] == {"success": False, "errors": "KeyError: 'citty'", "output": ""}


@pytest.mark.asyncio
async def test_blank_file_url_still_runs_code_that_loads_its_own_data(monkeypatch):
    """Only an unresolved File URL fails up front; a blank one runs the code with df=None."""
    seen = {}

    async def runner(code, params, **_kwargs):
        seen["df"] = params["df"]
        return {"result": None, "output": "", "errors": "", "script_error": "Error processing parameters: boom"}

    monkeypatch.setattr(workflow_utils, "execute_python_code", runner)
    result = await _node([]).process({"pythonCode": CODE, "fileUrl": ""})
    assert "df" in seen and seen["df"] is None
    assert is_node_failure(result)["error"] == "boom"


@pytest.mark.asyncio
async def test_printed_output_is_kept_when_the_code_fails(monkeypatch):
    from app.modules.workflow.engine.nodes.ml import ml_utils

    monkeypatch.setattr(ml_utils, "load_csv_file", lambda *a, **k: pd.DataFrame({"city": ["x"]}))

    async def no_extra_dirs():
        return []

    monkeypatch.setattr(ml_utils, "extra_csv_directories", no_extra_dirs)

    async def runner(*_args, **_kwargs):
        return {"result": None, "output": "Index(['city'])\n", "errors": "", "script_error": "Error processing parameters: boom"}

    monkeypatch.setattr(workflow_utils, "execute_python_code", runner)
    result = await _node(["a"]).process({"pythonCode": CODE, "fileUrl": "data.csv"})
    assert is_node_failure(result)["output"]["output"] == "Index(['city'])\n"
