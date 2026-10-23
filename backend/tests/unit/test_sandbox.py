import asyncio

import pandas as pd
import pytest

from app.modules.workflow.sandbox import SandboxViolation, validate_code_ast
from app.modules.workflow.utils import execute_python_code


class TestAllowedImports:
    def test_sklearn_import_and_transform_succeeds(self):
        code = """
from sklearn.preprocessing import StandardScaler

def executable_function(params):
    df = params["df"]
    scaler = StandardScaler()
    scaled = scaler.fit_transform(df[["a"]])
    return {"scaled_first": float(scaled[0][0])}

result = executable_function(params)
"""
        df = pd.DataFrame({"a": [1.0, 2.0, 3.0, 4.0, 5.0]})
        result = asyncio.run(execute_python_code(code, {"df": df}, wrap_code=False))

        assert result.get("error") is None
        assert result["result"]["scaled_first"] == pytest.approx(-1.414213562373095)

    def test_scipy_import_and_stats_call_succeeds(self):
        code = """
from scipy import stats

def executable_function(params):
    return {"zscore_first": float(stats.zscore(params["values"])[0])}

result = executable_function(params)
"""
        result = asyncio.run(
            execute_python_code(code, {"values": [1.0, 2.0, 3.0, 4.0, 5.0]}, wrap_code=False)
        )

        assert result.get("error") is None
        assert result["result"]["zscore_first"] == pytest.approx(-1.414213562373095)


class TestDisallowedImportsStillBlocked:
    def test_os_import_is_rejected(self):
        code = """
import os

def executable_function(params):
    return os.listdir("/")

result = executable_function(params)
"""
        result = asyncio.run(execute_python_code(code, {}, wrap_code=False))

        assert result.get("error") is not None
        assert "os" in result["error"]
        assert "not allowed" in result["error"]

    def test_subprocess_import_is_rejected(self):
        code = """
import subprocess

def executable_function(params):
    return subprocess.run(["echo", "hi"])

result = executable_function(params)
"""
        result = asyncio.run(execute_python_code(code, {}, wrap_code=False))

        assert result.get("error") is not None
        assert "subprocess" in result["error"]


class TestAstValidatorStillBlocksEscapeAttempts:
    def test_dunder_subclasses_is_blocked(self):
        with pytest.raises(SandboxViolation):
            validate_code_ast("().__class__.__bases__[0].__subclasses__()")

    def test_os_system_attribute_is_blocked(self):
        with pytest.raises(SandboxViolation):
            validate_code_ast("os.system('ls')")

    def test_ordinary_sklearn_usage_is_not_blocked(self):
        # fit/transform/fit_transform are ordinary attribute names, not in
        # any denylist - the AST validator must not false-positive on them.
        validate_code_ast(
            "from sklearn.preprocessing import StandardScaler\n"
            "StandardScaler().fit_transform(df)\n"
        )
