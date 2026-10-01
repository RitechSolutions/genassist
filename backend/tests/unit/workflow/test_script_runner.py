import pickle
import threading
import time

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


def test_sandbox_violation():
    response = _execute_python_code_sync("result = ().__class__", {}, wrap_code=False)

    assert response["error"].startswith("Sandbox violation:")


def test_encode_result_caps_size():
    too_large = pickle.loads(_encode_result({"result": "x" * 4096}, limit=1024))
    unpicklable = pickle.loads(_encode_result({"result": (i for i in range(3))}))

    assert too_large["error"].startswith("Result too large")
    assert pickle.loads(_encode_result({"result": 1}, limit=1024)) == {"result": 1}
    assert unpicklable["error"].startswith("Result could not be serialized")
