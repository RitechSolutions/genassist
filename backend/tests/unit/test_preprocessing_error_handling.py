"""
Tests for execute_and_process_preprocessing_code's error handling - the exact
bug behind DP-1 ("Got: NoneType" instead of the real error) and DP-2 (a
harmless warning failing the whole preprocessing run). Both came from the
same line checking the wrong response key - see ml_utils.py.
"""

import pandas as pd
import pytest

import app.modules.workflow.utils as workflow_utils
from app.core.exceptions.exception_classes import AppException
from app.modules.workflow.engine.nodes.ml.ml_utils import (
    execute_and_process_preprocessing_code,
)


class TestHardErrorsSurfaceTheRealMessage:
    """DP-1: a syntax error, blocked import, or timeout must surface its own
    specific message - never the generic 'Got: NoneType' guess."""

    @pytest.mark.asyncio
    async def test_syntax_error_message_is_surfaced(self, monkeypatch):
        monkeypatch.setattr(
            workflow_utils,
            "execute_python_code",
            lambda code, params, wrap_code=True: _response(
                {"error": "Syntax error: invalid syntax (line 3)", "errors": "", "output": ""}
            ),
        )
        with pytest.raises(AppException) as exc_info:
            await execute_and_process_preprocessing_code("bad code", None, pd.DataFrame(), "f.csv")
        assert "Syntax error: invalid syntax" in exc_info.value.error_detail
        assert "NoneType" not in exc_info.value.error_detail

    @pytest.mark.asyncio
    async def test_blocked_import_message_is_surfaced(self, monkeypatch):
        monkeypatch.setattr(
            workflow_utils,
            "execute_python_code",
            lambda code, params, wrap_code=True: _response(
                {"error": "Sandbox violation: import of 'os' is not allowed", "errors": "", "output": ""}
            ),
        )
        with pytest.raises(AppException) as exc_info:
            await execute_and_process_preprocessing_code("code", None, pd.DataFrame(), "f.csv")
        assert "import of 'os' is not allowed" in exc_info.value.error_detail

    @pytest.mark.asyncio
    async def test_timeout_message_is_surfaced(self, monkeypatch):
        monkeypatch.setattr(
            workflow_utils,
            "execute_python_code",
            lambda code, params, wrap_code=True: _response(
                {"error": "Execution timed out after 120 seconds", "errors": "", "output": ""}
            ),
        )
        with pytest.raises(AppException) as exc_info:
            await execute_and_process_preprocessing_code("code", None, pd.DataFrame(), "f.csv")
        assert "timed out after 120 seconds" in exc_info.value.error_detail

    @pytest.mark.asyncio
    async def test_raise_on_error_false_returns_the_real_message_not_nonetype(self, monkeypatch):
        monkeypatch.setattr(
            workflow_utils,
            "execute_python_code",
            lambda code, params, wrap_code=True: _response(
                {"error": "Execution timed out after 120 seconds", "errors": "", "output": ""}
            ),
        )
        df, error, response = await execute_and_process_preprocessing_code(
            "code", None, pd.DataFrame(), "f.csv", raise_on_error=False
        )
        assert df is None
        assert error == "Execution timed out after 120 seconds"


class TestUserCodeExceptionsSurfaceTheRealMessage:
    """DP-1: an exception raised by the user's own code. The execution
    wrapper catches it and reports it under "errors" (plural) with
    "Global errors:", not "error" - so these run the real sandbox instead
    of faking the response, which is what hid this case before."""

    @pytest.mark.asyncio
    async def test_value_error_in_user_code_is_surfaced(self):
        code = (
            "import pandas as pd\n"
            "def executable_function(params):\n"
            "    df = params['df']\n"
            "    df['a'] = df['a'].astype('Int64')\n"
            "    return df\n"
        )
        with pytest.raises(AppException) as exc_info:
            await execute_and_process_preprocessing_code(
                code, None, pd.DataFrame({"a": [1.5]}), "f.csv"
            )
        assert "cannot safely cast" in exc_info.value.error_detail
        assert "NoneType" not in exc_info.value.error_detail
        assert "Global errors" not in exc_info.value.error_detail

    @pytest.mark.asyncio
    async def test_user_exception_with_raise_on_error_false_returns_the_message(self):
        code = (
            "def executable_function(params):\n"
            "    raise KeyError('missing_column')\n"
        )
        df, error, response = await execute_and_process_preprocessing_code(
            code, None, pd.DataFrame({"a": [1]}), "f.csv", raise_on_error=False
        )
        assert df is None
        assert "missing_column" in error
        assert "NoneType" not in error

    @pytest.mark.asyncio
    async def test_real_pandas_future_warning_does_not_fail_the_run(self):
        # DP-2 end-to-end: this fillna on an object column emits a real
        # FutureWarning to stderr while still returning a valid DataFrame.
        code = (
            "import pandas as pd\n"
            "def executable_function(params):\n"
            "    df = params['df']\n"
            "    df['a'] = df['a'].fillna(0)\n"
            "    return df\n"
        )
        df, error, response = await execute_and_process_preprocessing_code(
            code, None, pd.DataFrame({"a": pd.Series([1, None], dtype=object)}), "f.csv"
        )
        assert error is None
        assert df["a"].tolist() == [1, 0]


class TestHarmlessWarningsDoNotFailTheRun:
    """DP-2: stderr output (e.g. a pandas FutureWarning, which Python prints
    to stderr by default) must not fail a run that produced a valid result."""

    @pytest.mark.asyncio
    async def test_stderr_warning_with_valid_dataframe_result_succeeds(self, monkeypatch):
        result_df = pd.DataFrame({"a": [1, 2, 3]})
        monkeypatch.setattr(
            workflow_utils,
            "execute_python_code",
            lambda code, params, wrap_code=True: _response(
                {
                    "result": result_df,
                    "error": None,
                    "errors": "FutureWarning: Downcasting object dtype arrays on .fillna is deprecated",
                    "output": "",
                }
            ),
        )
        df, error, response = await execute_and_process_preprocessing_code(
            "code", None, pd.DataFrame(), "f.csv"
        )
        assert error is None
        assert df is not None
        assert df["a"].tolist() == [1, 2, 3]


class TestNormalSuccessUnaffected:
    @pytest.mark.asyncio
    async def test_clean_success_with_no_errors_or_warnings(self, monkeypatch):
        result_df = pd.DataFrame({"a": [1]})
        monkeypatch.setattr(
            workflow_utils,
            "execute_python_code",
            lambda code, params, wrap_code=True: _response(
                {"result": result_df, "error": None, "errors": "", "output": ""}
            ),
        )
        df, error, response = await execute_and_process_preprocessing_code(
            "code", None, pd.DataFrame(), "f.csv"
        )
        assert error is None
        assert df["a"].tolist() == [1]

    @pytest.mark.asyncio
    async def test_genuinely_missing_result_still_reports_nonetype(self, monkeypatch):
        # No "error" key and no "result" key at all (e.g. code ran but never
        # set `result`) - this is the one case where the NoneType message is
        # still the correct, honest description of what happened.
        monkeypatch.setattr(
            workflow_utils,
            "execute_python_code",
            lambda code, params, wrap_code=True: _response(
                {"error": None, "errors": "", "output": ""}
            ),
        )
        with pytest.raises(AppException) as exc_info:
            await execute_and_process_preprocessing_code("code", None, pd.DataFrame(), "f.csv")
        assert "NoneType" in exc_info.value.error_detail


async def _response(d):
    return d


class TestLargeResultsDoNotHang:
    """A result bigger than the subprocess pipe buffer (~64 KB) - e.g. a real
    30k-row dataset - used to deadlock: the parent joined the child before
    reading its result, and the child can't exit until the result is read.
    The run then hung until the execution timeout killed it."""

    @pytest.mark.asyncio
    async def test_30k_row_dataframe_result_returns_without_timing_out(self, monkeypatch):
        import time

        import numpy as np

        # Short timeout so a regression fails fast instead of waiting 10 minutes.
        monkeypatch.setattr(workflow_utils, "_EXEC_TIMEOUT_SECONDS", 10)
        rng = np.random.default_rng(0)
        df = pd.DataFrame(rng.normal(size=(29757, 17)), columns=[f"c{i}" for i in range(17)])
        code = (
            "import pandas as pd\n"
            "def executable_function(params):\n"
            "    df = params['df']\n"
            "    df['c0'] = df['c0'].astype('float64')\n"
            "    return df\n"
        )
        started = time.monotonic()
        out, error, response = await execute_and_process_preprocessing_code(
            code, None, df, "f.csv", raise_on_error=False
        )
        elapsed = time.monotonic() - started
        assert error is None, error
        assert len(out) == 29757
        assert elapsed < 10, f"took {elapsed:.1f}s"


class TestRealErrorIsShownBeforeWarnings:
    """When a run fails after pandas printed a warning, the user's actual
    exception comes first in the message and the warning after it."""

    # stderr exactly as the sandbox returns it when user code raises after a
    # pandas FutureWarning (captured from a real run; pytest's own warning
    # capture stops the warning reaching stderr inside the test process).
    REAL_STDERR = (
        "<string>:4: FutureWarning: Downcasting object dtype arrays on .fillna, .ffill, "
        ".bfill is deprecated and will change in a future version.\n"
        "\nGlobal errors: Error processing parameters: real problem after the warning\n"
        "Traceback (most recent call last):\n"
        '  File "<string>", line 9, in <module>\n'
        '  File "<string>", line 5, in executable_function\n'
        "ValueError: real problem after the warning\n"
    )

    @pytest.mark.asyncio
    async def test_exception_after_a_future_warning_is_listed_first(self, monkeypatch):
        monkeypatch.setattr(
            workflow_utils,
            "execute_python_code",
            lambda code, params, wrap_code=True: _response(
                {"result": None, "output": "", "errors": self.REAL_STDERR}
            ),
        )
        df, error, response = await execute_and_process_preprocessing_code(
            "code", None, pd.DataFrame(), "f.csv", raise_on_error=False
        )
        assert df is None
        assert error.startswith("real problem after the warning")
        assert "ValueError: real problem after the warning" in error
        warnings_at = error.index("Warnings:")
        assert "FutureWarning" in error[warnings_at:]
        assert "FutureWarning" not in error[:warnings_at]

    @pytest.mark.asyncio
    async def test_raised_message_also_leads_with_the_real_error(self, monkeypatch):
        monkeypatch.setattr(
            workflow_utils,
            "execute_python_code",
            lambda code, params, wrap_code=True: _response(
                {"result": None, "output": "", "errors": self.REAL_STDERR}
            ),
        )
        with pytest.raises(AppException) as exc_info:
            await execute_and_process_preprocessing_code("code", None, pd.DataFrame(), "f.csv")
        assert exc_info.value.error_detail.startswith(
            "Error executing preprocessing code: real problem after the warning"
        )

    def test_formatting_without_warnings_or_marker(self):
        from app.modules.workflow.engine.nodes.ml.ml_utils import _format_user_code_error

        assert _format_user_code_error("\nGlobal errors: Error processing parameters: boom\ntb") == "boom\ntb"
        assert _format_user_code_error("  plain stderr  ") == "plain stderr"
