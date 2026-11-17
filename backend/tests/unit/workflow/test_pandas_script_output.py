"""pandas objects a script returns reach the engine, the response and conversation memory as plain JSON data."""

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


def _workflow(unwrap, node_type="pythonCodeNode", code_field="code"):
    return {
        "id": "test-workflow",
        "nodes": [
            {"id": "start", "type": "chatInputNode", "data": {"name": "Start", "inputSchema": {"message": {"type": "string", "required": True}}}},
            {"id": "py", "type": node_type, "data": {"name": "Script", code_field: "result = 1", "unwrap": unwrap}},
        ],
        "edges": [{"source": "start", "target": "py", "sourceHandle": "output", "targetHandle": "input"}],
    }


async def _run(monkeypatch, result, unwrap=False, module=python_tool_node, **workflow_options):
    async def runner(*_args, **_kwargs):
        return {"result": result, "output": "", "errors": ""}

    monkeypatch.setattr(module, "execute_python_code", runner)
    memory = MagicMock()
    memory.add_input_output = AsyncMock()
    with patch.object(WorkflowState, "get_memory", return_value=memory):
        state = await WorkflowEngine(_workflow(unwrap, **workflow_options)).execute_from_node(
            input_data={"message": "hi"}, persist=True, await_persist=True
        )
    memory.add_input_output.assert_awaited_once()
    stored = memory.add_input_output.await_args.args[1]
    return state, stored


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
async def test_python_node_pandas_result_completes_and_is_stored_in_memory(monkeypatch, result, unwrap, expected):
    state, stored = await _run(monkeypatch, result, unwrap)

    assert state.status == "completed"
    assert state.node_execution_status["py"]["status"] == "success"
    assert state.output == expected
    assert stored == expected
    json.dumps(stored)  # what the memory write does, without a fallback


@pytest.mark.asyncio
async def test_data_mapper_pandas_result_becomes_plain_data(monkeypatch):
    state, stored = await _run(
        monkeypatch, pd.DataFrame({"n": [1]}), module=data_mapper_node, node_type="dataMapperNode", code_field="pythonScript"
    )

    assert state.status == "completed"
    assert stored == {"result": [{"n": 1}], "output": "", "errors": ""}


@pytest.mark.asyncio
async def test_memory_stores_values_json_cannot_hold():
    redis = MagicMock()
    for method in ("exists", "hset", "expire", "lpush"):
        setattr(redis, method, AsyncMock())
    memory = RedisConversationMemory("thread-1")
    memory.redis_client = redis
    content = {"s": pd.Series([1]), "n": np.int64(3), "when": datetime.datetime(2024, 1, 1), "tags": {"x"}}

    await memory.add_message(Message("assistant", content))

    stored = json.loads(redis.lpush.await_args.args[1])["content"]
    assert stored == {"s": [1], "n": 3, "when": "2024-01-01T00:00:00", "tags": ["x"]}
