"""A script's pandas result stays a pandas object between nodes, and becomes plain data where JSON is needed:
the run response and conversation memory."""

import datetime
import json
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pandas as pd
import pytest

from app.modules.workflow.agents.memory import Message, RedisConversationMemory
from app.modules.workflow.engine.nodes import data_mapper_node, python_tool_node
from app.modules.workflow.engine.workflow_engine import WorkflowEngine
from app.modules.workflow.engine.workflow_state import WorkflowState
from app.modules.workflow.script_results import pandas_to_data


@pytest.mark.parametrize(
    "value, expected",
    [
        (pd.Series([1.5, 2.5]), [1.5, 2.5]),
        (pd.DataFrame({"n": [1, 2]}), [{"n": 1}, {"n": 2}]),
        # Filtering leaves an unnamed integer index, which says nothing about a row
        (pd.DataFrame({"n": [1, 2, 3]}).query("n > 1"), [{"n": 2}, {"n": 3}]),
        (pd.DataFrame({"n": [1, 2, 3]}).query("n > 1")["n"], [2, 3]),
        # Labels that mean something are kept
        (pd.Series(["a", "b", "a"], name="k").value_counts(), {"a": 2, "b": 1}),
        (
            pd.DataFrame({"k": ["a", "b"], "v": [1, 2]}).set_index("k"),
            [{"k": "a", "v": 1}, {"k": "b", "v": 2}],
        ),
        (
            pd.Series([1, 2], index=pd.MultiIndex.from_tuples([("a", 1), ("b", 2)], names=["k", "i"]), name="v"),
            [{"k": "a", "i": 1, "v": 1}, {"k": "b", "i": 2, "v": 2}],
        ),
        (pd.Series([1, 2], index=pd.Index(["x", "x"], name="s"), name="s"), [1, 2]),
        # Missing values, timestamps and numpy numbers
        (pd.Series([1.0, np.nan]), [1.0, None]),
        (pd.Series(pd.to_datetime(["2024-01-01", None])), ["2024-01-01T00:00:00.000", None]),
        (pd.DataFrame([[1, 2]], columns=["a", "a"]), {"columns": ["a", "a"], "data": [[1, 2]]}),
        (pd.DataFrame(), []),
    ],
)
def test_pandas_objects_become_plain_data(value, expected):
    converted = pandas_to_data(value)
    assert converted == expected
    json.dumps(converted)


def test_pandas_objects_nested_in_containers_are_converted():
    converted = pandas_to_data({"p": pd.Series([1.5]), "rows": [pd.DataFrame({"n": [1]})], "t": (pd.Series([2]),)})
    assert converted == {"p": [1.5], "rows": [[{"n": 1}]], "t": ([2],)}


def test_values_without_pandas_objects_are_left_alone():
    when = datetime.datetime(2024, 1, 1)
    value = {"a": [1, "x", None], "when": when}
    assert pandas_to_data(value) == value
    assert pandas_to_data(value)["when"] is when


START = {
    "id": "start",
    "type": "chatInputNode",
    "data": {"name": "Start", "inputSchema": {"message": {"type": "string", "required": True}}},
}


def _workflow(*scripts, node_type="pythonCodeNode", code_field="code"):
    """Chat Input -> one script node per (code, unwrap) -> Chat Output"""
    nodes, edges, previous = [START], [], "start"
    for index, (code, unwrap) in enumerate(scripts):
        node_id = f"script{index}"
        nodes.append({"id": node_id, "type": node_type, "data": {"name": node_id, code_field: code, "unwrap": unwrap}})
        edges.append({"source": previous, "target": node_id, "sourceHandle": "output", "targetHandle": "input"})
        previous = node_id
    nodes.append({"id": "out", "type": "chatOutputNode", "data": {"name": "Out"}})
    edges.append({"source": previous, "target": "out", "sourceHandle": "output", "targetHandle": "input"})
    return {"id": "test-workflow", "nodes": nodes, "edges": edges}


def _redis_memory():
    redis = MagicMock()
    for method in ("exists", "hset", "expire", "lpush"):
        setattr(redis, method, AsyncMock())
    memory = RedisConversationMemory("thread-1")
    memory.redis_client = redis
    return memory, redis


async def _run(workflow):
    memory, redis = _redis_memory()
    with patch.object(WorkflowState, "get_memory", return_value=memory):
        state = await WorkflowEngine(workflow).execute_from_node(
            input_data={"message": "hi"}, persist=True, await_persist=True
        )
    # lpush runs once per message, user's first; each holds the JSON the memory stored
    stored = [json.loads(call.args[1])["content"] for call in redis.lpush.await_args_list]
    return state, stored


def _scripted(monkeypatch, *results, module=python_tool_node):
    """Stand in for the sandbox: each call returns the next result and records the params it was given"""
    calls = []

    async def runner(_code, params=None, **_kwargs):
        calls.append(params)
        return {"result": results[len(calls) - 1], "output": "", "errors": ""}

    monkeypatch.setattr(module, "execute_python_code", runner)
    return calls


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "result, unwrap, expected",
    [
        (pd.Series([1.5, 2.5]), False, {"result": [1.5, 2.5], "output": "", "errors": ""}),
        (pd.Series([1.5, 2.5]), True, [1.5, 2.5]),
        ({"p": pd.Series([1.5, 2.5])}, False, {"result": {"p": [1.5, 2.5]}, "output": "", "errors": ""}),
        (pd.DataFrame({"n": [1, 2]}), True, [{"n": 1}, {"n": 2}]),
        (pd.DataFrame({"n": [1, 2]}), False, {"result": [{"n": 1}, {"n": 2}], "output": "", "errors": ""}),
    ],
)
async def test_pandas_result_completes_and_reaches_response_and_memory_as_plain_data(
    monkeypatch, result, unwrap, expected
):
    _scripted(monkeypatch, result)
    state, stored = await _run(_workflow(("code", unwrap)))

    response = state.format_state_as_response()
    json.dumps(response)
    assert state.status == "completed"
    assert response["status"] == "success"
    assert response["output"] == expected
    assert stored == ["hi", expected]


@pytest.mark.asyncio
@pytest.mark.parametrize("unwrap", [False, True])
@pytest.mark.parametrize(
    "frame, rows",
    [
        (pd.DataFrame({"k": ["a", "b"], "v": [1, 2]}).set_index("k"), [{"k": "a", "v": 1}, {"k": "b", "v": 2}]),
        (pd.DataFrame({"k": ["a", "b", "a"], "v": [1, 2, 3]}).groupby("k").sum(), [{"k": "a", "v": 4}, {"k": "b", "v": 2}]),
    ],
)
async def test_named_index_labels_reach_the_response_as_they_reach_memory(monkeypatch, frame, rows, unwrap):
    _scripted(monkeypatch, frame)
    state, stored = await _run(_workflow(("code", unwrap)))

    expected = rows if unwrap else {"result": rows, "output": "", "errors": ""}
    assert state.format_state_as_response()["output"] == expected
    assert stored[1] == expected


@pytest.mark.asyncio
@pytest.mark.parametrize("unwrap, key", [(False, "source.result"), (True, "source")])
async def test_next_script_still_gets_the_dataframe(monkeypatch, unwrap, key):
    frame = pd.DataFrame({"k": ["x", "y", "x"], "n": [1, 2, 3]})
    calls = _scripted(monkeypatch, frame, {"x_total": 4})
    state, _ = await _run(_workflow(("code", unwrap), (f"df = params.get('{key}')", False)))

    assert state.status == "completed"
    assert isinstance(calls[1][key], pd.DataFrame)
    pd.testing.assert_frame_equal(calls[1][key], frame)


@pytest.mark.asyncio
async def test_two_script_pandas_chain_runs_in_the_sandbox():
    first = "import pandas as pd\ndef executable_function(params):\n    return pd.DataFrame({'k': ['x', 'y', 'x'], 'n': [1, 2, 3]})\n"
    second = (
        "def executable_function(params):\n"
        "    df = params.get('source.result')\n"
        "    return {'type': type(df).__name__, 'x_total': int(df.groupby('k')['n'].sum()['x'])}\n"
    )
    state, stored = await _run(_workflow((first, False), (second, False)))

    response = state.format_state_as_response()
    assert response["output"]["result"] == {"type": "DataFrame", "x_total": 4}
    assert response["output"]["errors"] == ""
    assert stored[1]["result"] == {"type": "DataFrame", "x_total": 4}


@pytest.mark.asyncio
async def test_data_mapper_pandas_result_reaches_response_and_memory_as_plain_data(monkeypatch):
    _scripted(monkeypatch, pd.DataFrame({"n": [1]}), module=data_mapper_node)
    state, stored = await _run(_workflow(("code", False), node_type="dataMapperNode", code_field="pythonScript"))

    assert state.status == "completed"
    assert state.format_state_as_response()["output"] == {"result": [{"n": 1}], "output": "", "errors": ""}
    assert stored[1] == {"result": [{"n": 1}], "output": "", "errors": ""}


@pytest.mark.asyncio
async def test_memory_stores_values_json_cannot_hold():
    memory, redis = _redis_memory()
    content = {"s": pd.Series([1]), "n": np.int64(3), "when": datetime.datetime(2024, 1, 1), "tags": {"x"}}

    await memory.add_message(Message("assistant", content))

    stored = json.loads(redis.lpush.await_args.args[1])["content"]
    assert stored == {"s": [1], "n": 3, "when": "2024-01-01T00:00:00", "tags": ["x"]}
