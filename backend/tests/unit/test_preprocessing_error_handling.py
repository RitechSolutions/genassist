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
            lambda code, params, wrap_code=True, **kwargs: _response(
                {"error": "Syntax error: invalid syntax (line 3)", "errors": "", "output": ""}
            ),
        )
        with pytest.raises(AppException) as exc_info:
            await execute_and_process_preprocessing_code("bad code", pd.DataFrame(), "f.csv")
        assert "Syntax error: invalid syntax" in exc_info.value.error_detail
        assert "NoneType" not in exc_info.value.error_detail

    @pytest.mark.asyncio
    async def test_blocked_import_message_is_surfaced(self, monkeypatch):
        monkeypatch.setattr(
            workflow_utils,
            "execute_python_code",
            lambda code, params, wrap_code=True, **kwargs: _response(
                {"error": "Sandbox violation: import of 'os' is not allowed", "errors": "", "output": ""}
            ),
        )
        with pytest.raises(AppException) as exc_info:
            await execute_and_process_preprocessing_code("code", pd.DataFrame(), "f.csv")
        assert "import of 'os' is not allowed" in exc_info.value.error_detail

    @pytest.mark.asyncio
    async def test_timeout_message_is_surfaced(self, monkeypatch):
        monkeypatch.setattr(
            workflow_utils,
            "execute_python_code",
            lambda code, params, wrap_code=True, **kwargs: _response(
                {"error": "Execution timed out after 120 seconds", "errors": "", "output": ""}
            ),
        )
        with pytest.raises(AppException) as exc_info:
            await execute_and_process_preprocessing_code("code", pd.DataFrame(), "f.csv")
        assert "timed out after 120 seconds" in exc_info.value.error_detail

    @pytest.mark.asyncio
    async def test_raise_on_error_false_returns_the_real_message_not_nonetype(self, monkeypatch):
        monkeypatch.setattr(
            workflow_utils,
            "execute_python_code",
            lambda code, params, wrap_code=True, **kwargs: _response(
                {"error": "Execution timed out after 120 seconds", "errors": "", "output": ""}
            ),
        )
        df, error, response = await execute_and_process_preprocessing_code(
            "code", pd.DataFrame(), "f.csv", raise_on_error=False
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
                code, pd.DataFrame({"a": [1.5]}), "f.csv"
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
            code, pd.DataFrame({"a": [1]}), "f.csv", raise_on_error=False
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
            code, pd.DataFrame({"a": pd.Series([1, None], dtype=object)}), "f.csv"
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
            lambda code, params, wrap_code=True, **kwargs: _response(
                {
                    "result": result_df,
                    "error": None,
                    "errors": "FutureWarning: Downcasting object dtype arrays on .fillna is deprecated",
                    "output": "",
                }
            ),
        )
        df, error, response = await execute_and_process_preprocessing_code(
            "code", pd.DataFrame(), "f.csv"
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
            lambda code, params, wrap_code=True, **kwargs: _response(
                {"result": result_df, "error": None, "errors": "", "output": ""}
            ),
        )
        df, error, response = await execute_and_process_preprocessing_code(
            "code", pd.DataFrame(), "f.csv"
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
            lambda code, params, wrap_code=True, **kwargs: _response(
                {"error": None, "errors": "", "output": ""}
            ),
        )
        with pytest.raises(AppException) as exc_info:
            await execute_and_process_preprocessing_code("code", pd.DataFrame(), "f.csv")
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
            code, df, "f.csv", raise_on_error=False
        )
        elapsed = time.monotonic() - started
        assert error is None, error
        assert len(out) == 29757
        assert elapsed < 10, f"took {elapsed:.1f}s"


class TestFailedStepsShowAShortMessage:
    """DP-18: a failed step shows the exception only - not the wrapper's
    "Error processing parameters:" prefix, the traceback with server paths
    (/opt/venv/...) or library warnings. Those go to the server log."""

    # stderr as the sandbox returns it when user code raises after a pandas
    # FutureWarning, with a traceback reaching into the installed libraries
    REAL_STDERR = (
        "/opt/venv/lib/python3.12/site-packages/pandas/core/frame.py:4: FutureWarning: Downcasting object "
        "dtype arrays on .fillna is deprecated.\n"
        "\nGlobal errors: Error processing parameters: real problem after the warning\n"
        "Traceback (most recent call last):\n"
        '  File "<string>", line 9, in <module>\n'
        '  File "<string>", line 5, in executable_function\n'
        '  File "/opt/venv/lib/python3.12/site-packages/pandas/core/frame.py", line 4102, in __getitem__\n'
        "ValueError: real problem after the warning\n"
    )

    @pytest.mark.asyncio
    async def test_only_the_exception_is_returned(self, monkeypatch, caplog):
        monkeypatch.setattr(
            workflow_utils,
            "execute_python_code",
            lambda code, params, wrap_code=True, **kwargs: _response(
                {"result": None, "output": "", "errors": self.REAL_STDERR}
            ),
        )
        with caplog.at_level("WARNING"):
            df, error, _ = await execute_and_process_preprocessing_code(
                "code", pd.DataFrame(), "f.csv", raise_on_error=False
            )
        assert df is None
        assert error == "real problem after the warning"
        # The full text is kept server-side
        assert "/opt/venv" in caplog.text

    @pytest.mark.asyncio
    async def test_raised_detail_has_no_prefix_or_traceback(self, monkeypatch):
        monkeypatch.setattr(
            workflow_utils,
            "execute_python_code",
            lambda code, params, wrap_code=True, **kwargs: _response(
                {"result": None, "output": "", "errors": self.REAL_STDERR}
            ),
        )
        with pytest.raises(AppException) as exc_info:
            await execute_and_process_preprocessing_code("code", pd.DataFrame(), "f.csv")
        assert exc_info.value.error_detail == "real problem after the warning"

    @pytest.mark.asyncio
    async def test_real_pandas_error_is_short_and_names_the_step(self):
        """Real sandbox run: a step selecting a column that isn't there."""
        code = (
            "import pandas as pd\n"
            "def autogenerated_preprocessing_function(df):\n"
            "    df = df.copy()\n"
            "    # STEP_START:step_1:column_filter\n"
            "    # Filter columns\n"
            '    df = df[["citty"]]\n'
            "    # STEP_END:step_1:column_filter\n"
            "    return df\n"
            "def executable_function(params):\n"
            "    return autogenerated_preprocessing_function(params['df'])\n"
        )
        with pytest.raises(AppException) as exc_info:
            await execute_and_process_preprocessing_code(code, pd.DataFrame({"city": ["a"]}), "f.csv")
        detail = exc_info.value.error_detail
        assert detail == "Column Filter: KeyError: \"None of [Index(['citty'], dtype='object')] are in the [columns]\""
        for leaked in ("Traceback", "Error processing parameters", "site-packages", "File \""):
            assert leaked not in detail

    @pytest.mark.asyncio
    async def test_a_steps_own_column_check_reads_as_written(self):
        """The check the frontend generates (DP-19) is shown as it is."""
        code = (
            "import pandas as pd\n"
            "def autogenerated_preprocessing_function(df):\n"
            "    # STEP_START:step_1:change_dtype\n"
            "    # Check that the step's columns exist\n"
            '    _missing = [c for c in ["citty"] if c not in df.columns]\n'
            "    if _missing:\n"
            '        raise ValueError("Change Column Data Type: column(s) not found in the data: " + ", ".join(_missing))\n'
            "    # STEP_END:step_1:change_dtype\n"
            "    return df\n"
            "def executable_function(params):\n"
            "    return autogenerated_preprocessing_function(params['df'])\n"
        )
        with pytest.raises(AppException) as exc_info:
            await execute_and_process_preprocessing_code(code, pd.DataFrame({"city": ["a"]}), "f.csv")
        assert exc_info.value.error_detail == "Change Column Data Type: column(s) not found in the data: citty"

    def test_multi_line_message_keeps_the_real_type(self):
        from app.modules.workflow.engine.nodes.ml.ml_utils import _short_user_code_error

        raw = (
            "Error processing parameters: bad values\n0    a\nName: x, dtype: object\n"
            "Traceback (most recent call last):\n"
            '  File "<string>", line 3, in f\n'
            "KeyError: bad values\n0    a\nName: x, dtype: object\n"
            "note: added by add_note\n"
        )
        assert _short_user_code_error(raw) == "KeyError: bad values\n0    a\nName: x, dtype: object"

    @pytest.mark.asyncio
    async def test_warnings_only_stderr_is_not_shown(self, monkeypatch):
        """Code that returned nothing, with only a warning in stderr: no path is shown."""
        stderr = "/opt/venv/lib/python3.12/site-packages/pandas/core/frame.py:4: FutureWarning: x\n"
        monkeypatch.setattr(
            workflow_utils,
            "execute_python_code",
            lambda code, params, wrap_code=True, **kwargs: _response({"result": None, "output": "", "errors": stderr}),
        )
        _, error, _ = await execute_and_process_preprocessing_code(
            "code", pd.DataFrame(), "f.csv", raise_on_error=False
        )
        assert error.startswith("The preprocessing code returned nothing")
        assert "/opt/venv" not in error

    def test_formatting(self):
        from app.modules.workflow.engine.nodes.ml.ml_utils import _short_user_code_error

        tb = 'Traceback (most recent call last):\n  File "<string>", line 2, in f\nKeyError: \'x\'\n'
        assert _short_user_code_error(f"Error processing parameters: 'x'\n{tb}") == "KeyError: 'x'"
        tb_boom = tb.replace("KeyError: 'x'", "KeyError: boom")
        assert _short_user_code_error(f"\nGlobal errors: Error processing parameters: boom\n{tb_boom}") == "KeyError: boom"
        assert _short_user_code_error("  plain stderr  ") == "plain stderr"
        # Outside any step's markers, no step is named
        code = "a\n# STEP_START:s:column_filter\nb\n# STEP_END:s:column_filter\nc\n"
        tb5 = tb.replace("line 2", "line 5")
        assert _short_user_code_error(f"Error processing parameters: 'x'\n{tb5}", code) == "KeyError: 'x'"
        tb3 = tb.replace("line 2", "line 3")
        assert _short_user_code_error(f"Error processing parameters: 'x'\n{tb3}", code) == "Column Filter: KeyError: 'x'"
        # Moved step types (still run by older workflows' code) are named too
        moved = "a\n# STEP_START:s:feature_engineering\nb\n# STEP_END:s:feature_engineering\nc\n"
        assert (
            _short_user_code_error(f"Error processing parameters: 'x'\n{tb3}", moved)
            == "Feature Engineering: KeyError: 'x'"
        )
