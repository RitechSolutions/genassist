import pickle
import threading
import time

import asyncpg
import pytest

from app.modules.workflow import utils
from app.modules.workflow.utils import _encode_result, _execute_python_code_sync, execute_python_code


@pytest.mark.asyncio
async def test_roundtrip_result_output_and_errors():
    code = 'def executable_function(params):\n    print("hello")\n    return {"sum": params["a"] + params["b"]}\n'

    response = await execute_python_code(code, {"a": 1, "b": 2})

    assert response == {"result": {"sum": 3}, "output": "hello\n", "errors": ""}


def test_large_result_is_returned_promptly(monkeypatch):
    monkeypatch.setattr(utils, "_EXEC_TIMEOUT_SECONDS", 10)
    start = time.monotonic()

    response = _execute_python_code_sync("result = 'x' * (2 * 1024 * 1024)", {}, wrap_code=False)

    assert "error" not in response
    assert len(response["result"]) == 2 * 1024 * 1024
    assert time.monotonic() - start < 10


def test_result_cap_is_per_call():
    response = _execute_python_code_sync(
        "result = 'x' * (3 * 1024 * 1024)", {}, wrap_code=False, max_result_bytes=2 * 1024 * 1024
    )

    assert response["error"].startswith("Result too large")


def test_timeout_kills_the_child(monkeypatch, caplog):
    monkeypatch.setattr(utils, "_EXEC_TIMEOUT_SECONDS", 2)
    monkeypatch.setattr(utils, "_EXIT_GRACE_SECONDS", 30)
    start = time.monotonic()

    response = _execute_python_code_sync("while True:\n    pass", {}, wrap_code=False)

    assert response == {"error": "Execution timed out after 2 seconds", "traceback": "", "output": "", "errors": ""}
    assert time.monotonic() - start < 10
    assert "User code execution timed out after 2s — subprocess killed" in caplog.text


def test_child_exit_without_result():
    start = time.monotonic()

    response = _execute_python_code_sync("raise SystemExit(3)", {}, wrap_code=False)

    assert response["error"] == "Subprocess exited without returning a result"
    assert time.monotonic() - start < 10


def test_unpicklable_params_name_the_key():
    response = _execute_python_code_sync("result = 1", {"lock": threading.Lock()}, wrap_code=False)

    assert response["error"] == "Script params cannot be sent to the sandbox: lock"


def test_params_that_only_load_in_the_parent_name_the_key():
    response = _execute_python_code_sync("result = 1", {"rows": [asyncpg.Point(1.5, 2.5)]}, wrap_code=False)

    assert response["error"] == "Script params cannot be sent to the sandbox: rows"


def test_empty_exception_message_is_still_an_error():
    response = _execute_python_code_sync("assert False", {}, wrap_code=False)

    assert response["error"] == "AssertionError"


@pytest.mark.asyncio
async def test_parent_side_empty_exception_message_is_still_an_error(monkeypatch):
    def boom(*_args):
        raise MemoryError()

    monkeypatch.setattr(utils, "_execute_python_code_sync", boom)

    response = await execute_python_code("result = 1", {})

    assert response["error"] == "MemoryError"


def test_sandbox_violation():
    response = _execute_python_code_sync("result = ().__class__", {}, wrap_code=False)

    assert response["error"].startswith("Sandbox violation:")


def test_encode_result_caps_size():
    too_large = pickle.loads(_encode_result({"result": "x" * 4096}, limit=1024))
    unpicklable = pickle.loads(_encode_result({"result": (i for i in range(3))}))

    assert too_large["error"].startswith("Result too large")
    assert pickle.loads(_encode_result({"result": 1}, limit=1024)) == {"result": 1}
    assert unpicklable["error"].startswith("Result could not be serialized")


def test_encode_result_keeps_the_result_under_heavy_printing(monkeypatch):
    monkeypatch.setattr(utils, "_MAX_STREAM_CHARS", 8)

    payload = pickle.loads(_encode_result({"result": 1, "output": "0123456789", "errors": ""}, limit=1024))

    assert payload["result"] == 1
    assert payload["output"] == "0123\n... (2 chars cut) ...\n6789"


def test_script_failure_survives_the_stream_cut():
    code = (
        "def executable_function(params):\n"
        "    import traceback\n"
        "    for _ in range(8000):\n"
        "        try:\n"
        "            raise KeyError('row')\n"
        "        except KeyError:\n"
        "            traceback.print_exc()\n"
        "    raise ValueError('x' * 300_000)\n"
    )

    response = _execute_python_code_sync(code, {})
    failure = utils.script_error(response)

    assert response["result"] is None
    assert "chars cut" in response["errors"]
    assert failure.startswith("Error processing parameters: " + "x" * 1000)
    assert failure.endswith("chars total)") and len(failure) < 5000


def test_top_level_script_with_a_none_result_is_not_a_failure():
    response = _execute_python_code_sync("result = params.get('customer_email')", {})

    assert response["result"] is None
    assert "executable_function" in response["errors"]
    assert utils.script_error(response) == ""
